import asyncio, httpx
from fastapi import HTTPException
from ..core.config import settings

_client = httpx.AsyncClient(timeout=httpx.Timeout(240.0, connect=5.0))
_sem = asyncio.Semaphore(settings.llm_concurrency)
_waiting = 0

async def chat(messages, max_tokens=400, temperature=0.4, json_mode=False) -> str:
    global _waiting
    if _waiting >= settings.llm_max_queue:
        raise HTTPException(503, "Сервер занят, повторите через минуту", headers={"Retry-After": "30"})
    _waiting += 1
    try:
        async with _sem:
            payload = {"model": "local", "messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature, "cache_prompt": True}
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            r = await _client.post(f"{settings.llm_url}/v1/chat/completions", json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    finally:
        _waiting -= 1

async def embed(texts: list[str]) -> list[list[float]]:
    r = await _client.post(f"{settings.embed_url}/v1/embeddings", json={"model": "embed", "input": texts})
    r.raise_for_status()
    return [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]