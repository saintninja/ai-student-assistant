import json
import math
from fastapi import HTTPException

from app.repository import db
from app.ai.llm import chat
from app.ai.prompts import JUDGE_SYSTEM, hint_messages, FALLBACK_HINT
from app.ai.rag import retrieve
from app.services.utils import TOUCH, norm, leaks
from app.services.task_service import task_by_code 

async def open_attempt(user_id: int, task_id: int, mode: str) -> int:
    return await db.pool.fetchval(
        """INSERT INTO attempts(user_id, task_id, mode) VALUES($1,$2,$3)
        ON CONFLICT (user_id, task_id) WHERE solved_at IS NULL
        DO UPDATE SET mode = EXCLUDED.mode,
        last_activity_at = CASE WHEN now() - attempts.last_activity_at > interval '30 minutes'
        THEN now() ELSE attempts.last_activity_at END
        RETURNING id""", user_id, task_id, mode)

async def give_hint(user_id: int, code: str, question: str | None):
    task = await task_by_code(code)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    att = await db.pool.fetchrow(
        f"UPDATE attempts SET hints_used = hints_used + 1, {TOUCH} "
        "WHERE user_id=$1 AND task_id=$2 AND solved_at IS NULL RETURNING id, hints_used", user_id, task["id"])
    if not att:
        raise HTTPException(409, "Сначала откройте задачу (или она уже решена)")
    level = min(att["hints_used"], 3)
    text, cached = None, False
    if not question: 
        text = await db.pool.fetchval("SELECT text FROM task_hints WHERE task_id=$1 AND level=$2",
                                      task["id"], level)
        cached = text is not None
    if text is None:
        ctx = await retrieve(task["statement"], task["topic_id"], k=2, types=("theory", "example", "pitfall"))
        ok = False
        for strict in (False, True):
            text = (await chat(hint_messages(task, level, question, ctx, strict),
                               max_tokens=250, temperature=0.3)).strip()
            if not leaks(text, task):
                ok = True
                break
        if not ok:
            text = FALLBACK_HINT
    elif not question:
        await db.pool.execute("INSERT INTO task_hints VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                              task["id"], level, text)
    await db.pool.execute("INSERT INTO hint_requests(attempt_id, level, question, cached) VALUES($1,$2,$3,$4)",
                          att["id"], level, question, cached)
    return {"level": level, "hint": text, "hints_used": att["hints_used"]}

async def check_answer(task, answer: str) -> tuple[bool, str]:
    ref = task["reference_answer"] or " "
    if task["answer_type"] == "exact":
        return norm(answer) == norm(ref), " "
    if task["answer_type"] == "numeric":
        try:
            return math.isclose(float(answer.replace(",", ".")), float(ref.replace(",", ".")),
                                rel_tol=1e-6, abs_tol=1e-9), " "
        except ValueError:
            return False, "Ожидается число"
    raw = await chat([{"role": "system", "content": JUDGE_SYSTEM},
                      {"role": "user", "content": f"ЗАДАЧА:\n{task['statement']}\n\nЭТАЛОН:\n{task['reference_solution']}\n\nОТВЕТ СТУДЕНТА:\n{answer}"}],
                     max_tokens=150, temperature=0, json_mode=True)
    try:
        d = json.loads(raw)
        comment = str(d.get("comment", " "))[:300]
        return bool(d["correct"]), (" " if leaks(comment, task) else comment)
    except (ValueError, KeyError):
        raise HTTPException(503, "Не удалось проверить ответ, повторите")

async def submit(user_id: int, code: str, answer: str):
    task = await task_by_code(code)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    aid = await db.pool.fetchval(
        "SELECT id FROM attempts WHERE user_id=$1 AND task_id=$2 AND solved_at IS NULL", user_id, task["id"])
    if not aid:
        raise HTTPException(409, "Сначала откройте задачу (или она уже решена)")
    ok, comment = await check_answer(task, answer)
    async with db.pool.acquire() as c, c.transaction():
        await c.execute("INSERT INTO submissions(attempt_id, answer, is_correct, comment) VALUES($1,$2,$3,$4)",
                        aid, answer, ok, comment)
        if ok:
            await c.execute(f"UPDATE attempts SET solved_at = now(), {TOUCH} WHERE id=$1", aid)
        else:
            await c.execute(f"UPDATE attempts SET wrong_submissions = wrong_submissions + 1, {TOUCH} WHERE id=$1", aid)
    return {"correct": ok, "comment": comment}