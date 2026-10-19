import asyncio, secrets, time, jwt
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.repository import db
from app.core.config import settings

ph = PasswordHasher()
DUMMY_HASH = ph.hash("dummy")          
_bearer = HTTPBearer()
_fails: dict[str, list[float]] = {}    

def new_password(n: int = 10) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"   
    return "".join(secrets.choice(alphabet) for _ in range(n))

async def hash_pw(p: str) -> str:
    return await asyncio.to_thread(ph.hash, p)

async def verify_pw(h: str, p: str) -> bool:
    try:
        return await asyncio.to_thread(ph.verify, h, p)
    except Exception:
        return False

def check_lock(key: str, limit: int = 5, window: int = 300):
    now = time.time()
    _fails[key] = [t for t in _fails.get(key, []) if now - t < window]
    if len(_fails[key]) >= limit:
        raise HTTPException(429, "Слишком много попыток входа, подождите 5 минут")

def register_fail(key: str):
    _fails.setdefault(key, []).append(time.time())

def make_token(user) -> str:
    exp = int(time.time()) + settings.jwt_ttl_hours * 3600
    return jwt.encode({"sub": str(user["id"]), "role": user["role"], "exp": exp},
                      settings.jwt_secret, algorithm="HS256")

async def current_user(cred: HTTPAuthorizationCredentials = Depends(_bearer)):
    try:
        data = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Недействительный токен")
    u = await db.pool.fetchrow("SELECT id, ins, role FROM users WHERE id=$1 AND is_active", int(data["sub"]))
    if not u:
        raise HTTPException(401, "Пользователь отключён")
    return u

async def require_admin(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Только для администратора")
    return u