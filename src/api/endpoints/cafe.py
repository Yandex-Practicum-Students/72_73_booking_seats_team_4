import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.cafe import Cafe
from schemas.cafe import CafeCreate, CafeInfo, CafeUpdate

from core.db import get_session

cafe_router = APIRouter(prefix='/cafes', tags=['Кафе'])


@cafe_router.get(
    '',
    response_model=list[CafeInfo],
    summary='Получение списка кафе',
)
async def get_cafes(
    session: AsyncSession = Depends(get_session),
) -> list[Cafe]:
    """Получение списка кафе.

    Для администраторов и менеджеров - все кафе (с возможностью выбора),
    для пользователей - только активные.
    """
    pass


@cafe_router.post(
    '',
    response_model=CafeInfo,
    summary='Создание нового кафе',
)
async def create_cafe(
    cafe_create: CafeCreate,
    session: AsyncSession = Depends(get_session),
) -> Cafe:
    """Создает новое кафе.

    Только для администраторов и менеджеров.
    """
    pass


@cafe_router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Обновление информации о кафе по его ID',
)
async def update_cafe(
    cafe_id: uuid.UUID,
    cafe_update: CafeUpdate,
    session: AsyncSession = Depends(get_session),
) -> Cafe:
    """Обновление информации о кафе по его ID.

    Только для администраторов и менеджеров.
    """
    pass
