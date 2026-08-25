from typing import Annotated, AsyncIterator

from fastapi import Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.settings import settings

async_engine = create_async_engine(
    url=settings.db_url,
    pool_pre_ping=True,
)

session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Получение асинхронной сессии для FastAPI Depends."""
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as error:
            await session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f'Ошибка при работе с БД{error}',
            ) from error


DBSession = Annotated[AsyncSession, Depends(get_session)]
