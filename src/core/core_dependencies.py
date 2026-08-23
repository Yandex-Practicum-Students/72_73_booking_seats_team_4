from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .redis import get_redis_session

redis_dep = Annotated[Redis, Depends(get_redis_session)]
db_dep = Annotated[AsyncSession, Depends(get_session)]
