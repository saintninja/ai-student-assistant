from fastapi import APIRouter, Depends, HTTPException

from app.schemas.task import TaskRequest, HintIn, SubmitIn
from app.services import services as S
from app.core.security import current_user
from app.repository import db

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/disciplines")
async def disciplines(_=Depends(current_user)):
    return await db.pool.fetch("SELECT id, code, title FROM disciplines ORDER BY title")

@router.get("/disciplines/{did}/topics")
async def topics(did: int, _=Depends(current_user)):
    return await db.pool.fetch("SELECT id, title, description FROM topics WHERE discipline_id=$1 ORDER BY id", did)

@router.post("/request")
async def request_task(r: TaskRequest, u=Depends(current_user)):
    code = S.extract_task_code(r.text)
    if code: 
        task = await S.task_by_code(code)
        if not task:
            raise HTTPException(404, f"Задача {code} не найдена")
        mode = "topic"
    elif r.mode == "general":
        task, mode = await S.pick_general(u["id"], r.discipline_id), "general"
    else:
        if not r.topic_id:
            raise HTTPException(422, "Укажите topic_id")
        mode = "topic"
        if r.mode == "topic_generate":
            task = await S.generate_task(r.topic_id, r.text)
        else:
            task = await S.pick_existing(u["id"], r.topic_id) or await S.generate_task(r.topic_id, r.text)
    
    await S.open_attempt(u["id"], task["id"], mode)
    return S.public(task)

@router.get("/{code}")
async def get_task(code: str, u=Depends(current_user)):
    task = await S.task_by_code(code)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    await S.open_attempt(u["id"], task["id"], "topic")
    return S.public(task)

@router.post("/{code}/hint")
async def hint(code: str, b: HintIn, u=Depends(current_user)):
    return await S.give_hint(u["id"], code, b.question)

@router.post("/{code}/submit")
async def submit(code: str, b: SubmitIn, u=Depends(current_user)):
    return await S.submit(u["id"], code, b.answer)

@router.get("/me/stats")
async def my_stats(u=Depends(current_user)):
    return await db.pool.fetch("SELECT * FROM v_student_topic_stats WHERE user_id=$1 ORDER BY discipline, topic", u["id"])