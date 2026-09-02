from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends, Request
from redis.asyncio import Redis


async def get_redis_session(request: Request) -> AsyncGenerator[Any, None]:
    """Асинхронный генератор сессии Redis."""
    async with request.app.state.redis.client() as client:
        yield client


redis_dep = Annotated[Redis, Depends(get_redis_session)]
