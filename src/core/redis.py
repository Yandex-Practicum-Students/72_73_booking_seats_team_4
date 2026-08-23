from typing import Any, AsyncGenerator

from fastapi import Request


async def get_redis_session(request: Request) -> AsyncGenerator[Any, None]:
    """Асинхронный генератор сессии Redis."""
    async with request.app.state.redis.client() as client:
        yield client
