from fastapi import APIRouter, HTTPException

from app.schemas.auth import LoginIn
from app.core.security import check_lock, register_fail, verify_pw, DUMMY_HASH, make_token
from app.repository import db

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(b: LoginIn):
    check_lock(b.ins)
    u = await db.pool.fetchrow("SELECT * FROM users WHERE ins=$1 AND is_active", b.ins)
    if not await verify_pw(u["password_hash"] if u else DUMMY_HASH, b.password) or not u:
        register_fail(b.ins)
        raise HTTPException(401, "Неверный ИНС или пароль")
    return {"access_token": make_token(u), "role": u["role"], "full_name": u["full_name"]}