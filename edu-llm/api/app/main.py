from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.repository import db
from app.core.security import hash_pw

from app.api.v1 import auth, tasks, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool(settings.database_url)
    if not await db.pool.fetchval("SELECT 1 FROM users WHERE role='admin'"):
        await db.pool.execute(
            "INSERT INTO users(ins, full_name, role, password_hash) VALUES('ADMIN','Администратор','admin',$1)",
            await hash_pw(settings.admin_password)
        )
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")