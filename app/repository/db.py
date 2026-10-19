import asyncpg
from pgvector.asyncpg import register_vector

pool: asyncpg.Pool = None

async def init_pool(dsn: str):
    global pool
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, init=register_vector)