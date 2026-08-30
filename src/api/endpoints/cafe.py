import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.cafe import get_cafe_or_404
from api.dependencies.permissions import AdminUser, CurrentUser, StaffUser
from api.responses import error_responses
from api.responses.statuses import CREATED, RESOURCE_CREATE, RESOURCE_DETAIL, RESOURCE_LIST, RESOURCE_UPDATE
from crud.cafe import cafe_crud
from models.cafe import Cafe
from models.user import UserRole
from schemas.cafe import CafeCreate, CafeInfo, CafeUpdate
from services.cafe import create_cafe as create_cafe_service
from services.cafe import ensure_manager_cafe_access, get_manager_cafes
from services.cafe import update_cafe as update_cafe_service

from core.core_dependencies import redis_dep
from core.db import DBSession

router = APIRouter()


@router.get(
    '',
    response_model=list[CafeInfo],
    responses=error_responses(*RESOURCE_LIST),
    summary='Список кафе',
)
async def get_cafes(
    current_user: CurrentUser,
    session: DBSession,
    show_active: Optional[bool] = Query(None),
) -> list[Cafe]:
    """Получение списка кафе.

    Для администраторов - все кафе (учитываем параметр show_active),
    для менеджеров и пользователей - только активные.
    """
    if current_user.role == UserRole.ADMIN:
        return await cafe_crud.get_all(
            session=session,
            show_active=show_active,
        )

    if current_user.role == UserRole.MANAGER:
        return await get_manager_cafes(current_user, session, cafe_crud)

    return await cafe_crud.get_all(
        session=session,
        show_active=True,
    )


@router.post(
    '',
    response_model=CafeInfo,
    status_code=CREATED,
    responses=error_responses(*RESOURCE_CREATE),
    summary='Создание нового кафе',
)
async def create_cafe(
    cafe_create: CafeCreate,
    _: AdminUser,
    session: DBSession,
    redis: redis_dep,
) -> Cafe:
    """Создание нового кафе.

    Только для администраторов.
    """
    return await create_cafe_service(cafe_create, session, redis)


@router.get(
    '/{cafe_id}',
    response_model=CafeInfo,
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Информация о кафе по его ID',
)
async def get_cafe_by_id(
    cafe_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> Cafe:
    """Получение информации о кафе по его ID.

    Для администраторов и менеджеров - все кафе,
    для пользователей - только активные.
    """
    ensure_manager_cafe_access(current_user, cafe_id)

    if current_user.role == UserRole.USER and not cafe.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кафе не найдено',
        )

    return cafe


@router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    responses=error_responses(*RESOURCE_UPDATE),
    summary='Обновление информации о кафе по его ID',
)
async def update_cafe(
    cafe_id: uuid.UUID,
    cafe_update: CafeUpdate,
    _: StaffUser,
    session: DBSession,
    redis: redis_dep,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> Cafe:
    """Обновление информации о кафе по его ID.

    Только для администраторов и менеджеров.
    """
    ensure_manager_cafe_access(_, cafe_id)
    return await update_cafe_service(cafe, cafe_update, session, redis)
