import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.table import Table
from schemas.table import TableCreate, TableInfo, TableUpdate

from core.db import get_session

table_router = APIRouter(prefix='/cafes/{cafe_id}/tables', tags=['Столы'])


@table_router.get(
    '',
    response_model=list[TableInfo],
    summary='Список столов в кафе',
)
async def get_tables_by_cafe(
    session: AsyncSession = Depends(get_session),
) -> list[Table]:
    """Получение списка доступных для бронирования столов в кафе.

    Для администраторов и менеджеров - все столы (с возможностью выбора),
    для пользователей - только активные.
    """


@table_router.post(
    '',
    response_model=TableInfo,
    summary='Новый стол в кафе',
)
async def create_cafe(
    table_create: TableCreate,
    session: AsyncSession = Depends(get_session),
) -> Table:
    """Создает новый стол кафе.

    Только для администраторов и менеджеров.
    """


@table_router.patch(
    '/{table_id}',
    response_model=TableInfo,
    summary='Обновление информации о столе в кафе по его ID',
)
async def update_table(
    table_id: uuid.UUID,
    table_update: TableUpdate,
    session: AsyncSession = Depends(get_session),
) -> Table:
    """Обновление информации о столе в кафе по его ID.

    Только для администраторов и менеджеров.
    """
