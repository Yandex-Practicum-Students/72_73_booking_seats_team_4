import uuid

from fastapi import APIRouter, Depends

from api.dependencies.cafe import get_cafe_or_404
from api.dependencies.filters import Boolean, filter_user_role_manager_for_cafe_id, resolve_show_active
from api.dependencies.permissions import CurrentUser, StaffUser, ensure_active_resource_visible
from api.dependencies.tables import get_table_in_cafe
from api.responses import error_responses
from api.responses.statuses import CREATED, RESOURCE_CREATE_WITH_PARENT, RESOURCE_DETAIL, RESOURCE_UPDATE
from crud.table import table_crud
from models import Cafe, Table
from schemas.table import TableCreate, TableInfo, TableUpdate
from services.cafe import ensure_manager_cafe_access

from core.db import DBSession
from core.redis import redis_dep

router = APIRouter()


@router.get(
    '',
    response_model=list[TableInfo],
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Список столов в кафе',
)
async def get_tables_by_cafe(
    cafe_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    show_active: Boolean = None,
    _cafe: Cafe = Depends(get_cafe_or_404),
) -> list[Table]:
    """Получение списка доступных для бронирования столов в кафе.

    Для администраторов - все столы (учитываем параметр show_active),
    для менеджеров и пользователей - только активные.
    """
    show_active = resolve_show_active(current_user, show_active)
    cafe_id = filter_user_role_manager_for_cafe_id(current_user, cafe_id)
    return await table_crud.get_by_cafe(
        cafe_id=cafe_id,
        session=session,
        show_active=show_active,
    )


@router.post(
    '',
    response_model=TableInfo,
    status_code=CREATED,
    responses=error_responses(*RESOURCE_CREATE_WITH_PARENT),
    summary='Новый стол в кафе',
)
async def create_table(
    cafe_id: uuid.UUID,
    table_create: TableCreate,
    user: StaffUser,
    session: DBSession,
    _cafe: Cafe = Depends(get_cafe_or_404),
) -> Table:
    """Создание нового стола в кафе.

    Менеджер создает столы только в своём кафе.
    Администратор создает в любом кафе.
    """
    ensure_manager_cafe_access(user, cafe_id)
    return await table_crud.create_with_cafe(cafe_id, table_create, session)


@router.get(
    '/{table_id}',
    response_model=TableInfo,
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Информация о столе в кафе по его ID',
)
async def get_table_by_id(
    cafe_id: uuid.UUID,
    table_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    table: Table = Depends(get_table_in_cafe),
) -> Table:
    """Получение информации о столе в кафе по его ID.

    Для администраторов и менеджеров - все столы,
    для пользователей - только активные.
    """
    ensure_manager_cafe_access(current_user, cafe_id)

    ensure_active_resource_visible(current_user, table, 'Стол не найден')

    return table


@router.patch(
    '/{table_id}',
    response_model=TableInfo,
    responses=error_responses(*RESOURCE_UPDATE),
    summary='Обновление информации о столе в кафе по его ID',
)
async def update_table(
    cafe_id: uuid.UUID,
    table_id: uuid.UUID,
    table_update: TableUpdate,
    user: StaffUser,
    session: DBSession,
    redis: redis_dep,
    table: Table = Depends(get_table_in_cafe),
) -> Table:
    """Обновление информации о столе в кафе по его ID.

    Только для администраторов и менеджеров.
    """
    ensure_manager_cafe_access(user, cafe_id)
    return await table_crud.update(table, table_update, session, redis)
