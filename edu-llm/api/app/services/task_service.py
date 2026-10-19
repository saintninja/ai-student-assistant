import random
from fastapi import HTTPException
from pydantic import ValidationError

from app.repository import db
from app.ai.llm import chat, embed
from app.ai.prompts import gen_messages
from app.ai.rag import retrieve
from app.schemas.task import GeneratedTask
from app.services.utils import TASK_SQL, SERVABLE

async def task_by_code(code: str):
    return await db.pool.fetchrow(TASK_SQL + "WHERE k.code=$1 AND k.status<>'rejected'", code.upper())

async def task_by_id(task_id: int):
    return await db.pool.fetchrow(TASK_SQL + "WHERE k.id=$1", task_id)

async def pick_existing(user_id: int, topic_id: int):
    tid = await db.pool.fetchval(
        f"""SELECT k.id FROM tasks k
        LEFT JOIN attempts a ON a.task_id=k.id AND a.user_id=$1
        WHERE k.topic_id=$2 AND {SERVABLE}
        GROUP BY k.id
        ORDER BY (count(a.id)=0) DESC, max(a.solved_at) ASC NULLS FIRST, k.difficulty, random()
        LIMIT 1""", user_id, topic_id)
    return await task_by_id(tid) if tid else None

async def pick_general(user_id: int, discipline_id: int | None):
    topics = await db.pool.fetch(
        f"""SELECT t.id, (coalesce(sum(v.w),0) + 1.0) / (count(v.w) + 2) AS weakness
        FROM topics t LEFT JOIN v_attempt_weakness v ON v.topic_id=t.id AND v.user_id=$1
        WHERE ($2::int IS NULL OR t.discipline_id=$2)
        AND EXISTS (SELECT 1 FROM tasks k WHERE k.topic_id=t.id AND {SERVABLE})
        GROUP BY t.id """, user_id, discipline_id)
    
    if not topics:
        raise HTTPException(404, "Нет доступных задач")
    
    topic = random.choices(topics, weights=[r["weakness"] ** 2 + 0.02 for r in topics])[0]
    
    tid = await db.pool.fetchval(
        f"""SELECT k.id FROM tasks k LEFT JOIN v_attempt_weakness v ON v.task_id=k.id AND v.user_id=$1
        WHERE k.topic_id=$2 AND {SERVABLE}
        GROUP BY k.id ORDER BY coalesce(avg(v.w), 0.5) DESC, random() LIMIT 1 """,
        user_id, topic["id"])
    return await task_by_id(tid)

async def generate_task(topic_id: int, wish: str | None):
    topic = await db.pool.fetchrow(
        """SELECT t.title AS topic, t.id, d.title AS discipline FROM topics t
        JOIN disciplines d ON d.id=t.discipline_id WHERE t.id=$1 """, topic_id)
    if not topic:
        raise HTTPException(404, "Тема не найдена")
    ctx = await retrieve(f"{topic['topic']} {wish or ''}", topic_id, k=3, types=("theory", "example", "task_pattern"))
    ex = [r["statement"][:200] for r in await db.pool.fetch(
        "SELECT statement FROM tasks WHERE topic_id=$1 ORDER BY random() LIMIT 3", topic_id)]
    msgs = gen_messages({"discipline": topic["discipline"], "topic": topic["topic"]}, ctx, ex, wish)
    for _ in range(3):
        raw = await chat(msgs, max_tokens=900, temperature=0.7, json_mode=True)
        try:
            g = GeneratedTask.model_validate_json(raw)
        except ValidationError:
            continue
        [vec] = await embed([g.statement])
        if await db.pool.fetchval("SELECT 1 FROM tasks WHERE topic_id=$1 AND embedding <-> $2 < 0.08 LIMIT 1",
                                  topic_id, vec):
            continue  # repeat
        async with db.pool.acquire() as c, c.transaction():
            tid = await c.fetchval(
                """INSERT INTO tasks(topic_id,title,statement,difficulty,answer_type,reference_answer,
                reference_solution,expected_minutes,source,status,embedding)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,'generated','auto',$9) RETURNING id """,
                topic_id, g.title, g.statement, g.difficulty, g.answer_type, g.reference_answer,
                g.reference_solution, g.expected_minutes, vec)
            
            await c.executemany("INSERT INTO task_hints(task_id, level, text) VALUES($1,$2,$3)",
                                [(tid, i + 1, h) for i, h in enumerate(g.hints)])
            return await task_by_id(tid)
    raise HTTPException(503, "Не удалось сгенерировать задачу, возьмите существующую")