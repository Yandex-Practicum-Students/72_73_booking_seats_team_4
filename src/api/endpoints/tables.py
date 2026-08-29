import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.cafe import get_cafe_or_404
from api.dependencies.permissions import CurrentUser, StaffUser
from api.dependencies.tables import get_table_in_cafe
from api.responses import error_responses
from crud.table import table_crud
from models import Cafe, Table
from models.user import UserRole
from schemas.table import TableCreate, TableInfo, TableUpdate
from services.cafe import ensure_manager_cafe_access

from core.core_dependencies import redis_dep
from core.db import DBSession

GET_RESPONSES = (
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
)

POST_RESPONSES = (
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
)

PATCH_RESPONSES = (
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
)

router = APIRouter()


@router.get(
    '',
    response_model=list[TableInfo],
    responses=error_responses(*GET_RESPONSES),
    summary='Список столов в кафе',
)
async def get_tables_by_cafe(
    cafe_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    show_active: Optional[bool] = Query(None),
    _cafe: Cafe = Depends(get_cafe_or_404),
) -> list[Table]:
    """Получение списка доступных для бронирования столов в кафе.

    Для администраторов - все столы (учитываем параметр show_active),
    для менеджеров и пользователей - только активные.
    """
    if current_user.role == UserRole.ADMIN:
        return await table_crud.get_by_cafe(
            cafe_id=cafe_id,
            session=session,
            show_active=show_active,
        )

    return await table_crud.get_by_cafe(
        cafe_id=cafe_id,
        session=session,
        show_active=True,
    )


@router.post(
    '',
    response_model=TableInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(*POST_RESPONSES),
    summary='Новый стол в кафе',
)
async def create_table(
    cafe_id: uuid.UUID,
    table_create: TableCreate,
    _: StaffUser,
    session: DBSession,
    _cafe: Cafe = Depends(get_cafe_or_404),
) -> Table:
    """Создание нового стола в кафе.

    Менеджер создает столы только в своём кафе.
    Администратор создает в любом кафе.
    """
    ensure_manager_cafe_access(_, cafe_id)
    return await table_crud.create_with_cafe(cafe_id, table_create, session)


@router.get(
    '/{table_id}',
    response_model=TableInfo,
    responses=error_responses(*GET_RESPONSES),
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

    if current_user.role == UserRole.USER and not table.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Стол не найден',
        )

    return table


@router.patch(
    '/{table_id}',
    response_model=TableInfo,
    responses=error_responses(*PATCH_RESPONSES),
    summary='Обновление информации о столе в кафе по его ID',
)
async def update_table(
    cafe_id: uuid.UUID,
    table_id: uuid.UUID,
    table_update: TableUpdate,
    _: StaffUser,
    session: DBSession,
    redis: redis_dep,
    table: Table = Depends(get_table_in_cafe),
) -> Table:
    """Обновление информации о столе в кафе по его ID.

    Только для администраторов и менеджеров.
    """
    ensure_manager_cafe_access(_, cafe_id)
    return await table_crud.update(table, table_update, session, redis)
