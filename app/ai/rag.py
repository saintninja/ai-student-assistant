import hashlib, re
from ..repository import db
from .llm import embed

def chunk_markdown(text: str, max_chars: int = 1200) -> list[tuple[str, str]]:
    out = []
    for sec in re.split(r"\n(?=## )", text.strip()):
        head = sec.split("\n", 1)[0].lstrip("# ").strip()
        buf = ""
        for p in re.split(r"\n\s*\n", sec):
            if buf and len(buf) + len(p) > max_chars:
                out.append((head, buf.strip()))
                buf = f"## {head}\n"
            buf += p + "\n\n"
        if buf.strip():
            out.append((head, buf.strip()))
    return out

async def ingest(discipline_code, topic_title, doc_type, title, source, text):
    row = await db.pool.fetchrow(
        """SELECT d.id AS did, t.id AS tid FROM disciplines d
           LEFT JOIN topics t ON t.discipline_id=d.id AND t.title=$2 WHERE d.code=$1""",
        discipline_code, topic_title)
    if not row:
        raise ValueError("Неизвестная дисциплина")
    chunks = chunk_markdown(text)
    vecs = []
    for i in range(0, len(chunks), 16):
        vecs += await embed([c[1] for c in chunks[i:i + 16]])
    async with db.pool.acquire() as c, c.transaction():
        await c.execute("DELETE FROM kb_documents WHERE discipline_id=$1 AND topic_id IS NOT DISTINCT FROM $2 AND title=$3",
                        row["did"], row["tid"], title)         
        doc_id = await c.fetchval(
            """INSERT INTO kb_documents(discipline_id, topic_id, doc_type, title, source, checksum)
               VALUES($1,$2,$3,$4,$5,$6) RETURNING id""",
            row["did"], row["tid"], doc_type, title, source, hashlib.sha256(text.encode()).hexdigest())
        await c.executemany(
            """INSERT INTO kb_chunks(document_id, discipline_id, topic_id, doc_type, chunk_index, heading, content, embedding)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
            [(doc_id, row["did"], row["tid"], doc_type, i, h, t, v)
             for i, ((h, t), v) in enumerate(zip(chunks, vecs))])
    return len(chunks)

async def retrieve(query: str, topic_id: int, k: int = 3, types: tuple | None = None):
    [qv] = await embed([query])
    return await db.pool.fetch(
        """SELECT heading, content, doc_type, embedding <=> $1 AS dist
           FROM kb_chunks
           WHERE topic_id = $2 AND ($3::text[] IS NULL OR doc_type = ANY($3))
           ORDER BY embedding <=> $1 LIMIT $4""",
        qv, topic_id, list(types) if types else None, k)