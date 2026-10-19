from fastapi import APIRouter, Depends, HTTPException
from typing import Literal

from app.schemas.admin import StudentIn, TaskIn, KBIn
from app.core.security import require_admin
from app.services import services as S
from app.ai import rag
from app.ai.llm import embed
from repository import db
from app.core.security import new_password, hash_pw

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/stats")
async def admin_stats(discipline_id: int | None = None, ins: str | None = None, _=Depends(require_admin)):
    return await db.pool.fetch(
        """SELECT * FROM v_student_topic_stats
        WHERE ($1::int IS NULL OR discipline_id=$1) AND ($2::text IS NULL OR ins=$2)
        ORDER BY ins, discipline, topic""", discipline_id, ins)

@router.post("/students/bulk")
async def create_students(items: list[StudentIn], _=Depends(require_admin)):
    out = []
    for s in items:
        pw = new_password()
        ins = await db.pool.fetchval(
            "INSERT INTO users(ins, full_name, group_name, password_hash) VALUES($1,$2,$3,$4)"
            "ON CONFLICT (ins) DO NOTHING RETURNING ins", 
            s.ins, s.full_name, s.group_name, await hash_pw(pw))
        if ins:
            out.append({"ins": s.ins, "full_name": s.full_name, "password": pw})
    return out

@router.post("/students/{ins}/reset-password")
async def reset_password(ins: str, _=Depends(require_admin)):
    pw = new_password()
    if not await db.pool.fetchval("UPDATE users SET password_hash=$2 WHERE ins=$1 RETURNING 1", ins, await hash_pw(pw)):
        raise HTTPException(404, "Студент не найден")
    return {"ins": ins, "password": pw}

@router.post("/tasks")
async def import_task(t: TaskIn, _=Depends(require_admin)):
    topic_id = await db.pool.fetchval(
        "SELECT t.id FROM topics t JOIN disciplines d ON d.id=t.discipline_id WHERE d.code=$1 AND t.title=$2",
        t.discipline, t.topic)
    if not topic_id:
        raise HTTPException(404, "Тема не найдена")
    
    [vec] = await embed([t.statement])
    async with db.pool.acquire() as c, c.transaction():
        row = await c.fetchrow(
            "INSERT INTO tasks(topic_id,title,statement,difficulty,answer_type,reference_answer,"
            "reference_solution,expected_minutes,source,status,embedding)"
            "VALUES($1,$2,$3,$4,$5,$6,$7,$8,'manual','approved',$9) RETURNING id, code",
            topic_id, t.title, t.statement, t.difficulty, t.answer_type, t.reference_answer,
            t.reference_solution, t.expected_minutes, vec)
        
        await c.executemany("INSERT INTO task_hints VALUES($1,$2,$3)",
                            [(row["id"], i + 1, h) for i, h in enumerate(t.hints[:3])])
    return {"code": row["code"]}

@router.patch("/tasks/{code}/status")
async def set_status(code: str, status: Literal["approved", "rejected"], _=Depends(require_admin)):
    await db.pool.execute("UPDATE tasks SET status=$2 WHERE code=$1", code.upper(), status)
    return {"ok": True}

@router.post("/kb/ingest")
async def kb_ingest(d: KBIn, _=Depends(require_admin)):
    n = await rag.ingest(d.discipline, d.topic, d.doc_type, d.title, d.source, d.text)
    return {"chunks": n}