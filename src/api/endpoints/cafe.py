import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.permissions import AdminUser, CurrentUser, StaffUser
from api.dependencies.tables import get_cafe_or_404, require_manager_cafe_access
from api.responses import error_responses
from crud.cafe import cafe_crud
from models import Cafe
from models.user import UserRole
from schemas.cafe import CafeCreate, CafeInfo, CafeUpdate

from core.db import DBSession
from core.core_dependencies import redis_dep

router = APIRouter()


@router.get(
    '',
    response_model=list[CafeInfo],
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Получение списка кафе',
)
async def get_cafes(
    current_user: CurrentUser,
    session: DBSession,
    show_active: Optional[bool] = Query(None),
) -> list[Cafe]:
    """Получение списка кафе.

    Для администраторов все кафе (с фильтром по show_active),
    для менеджеров только свое кафе (игнорирует show_active),
    для пользователей - только активные (игнорирует show_active).
    """
    if current_user.role == UserRole.ADMIN:
        return await cafe_crud.get_all(session=session, show_active=show_active)

    if current_user.role == UserRole.MANAGER:
        if current_user.cafe_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Менеджер не привязан к кафе',
            )
        cafe = await cafe_crud.get(current_user.cafe_id, session)
        return [cafe] if cafe else []

    return await cafe_crud.get_all(session=session, show_active=True)


@router.get(
    '/{cafe_id}',
    response_model=CafeInfo,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Получение информации о кафе по его ID',
)
async def get_cafe_by_id(
    cafe_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> Cafe:
    """Получение информации о кафе по его ID.

    Для администраторов все кафе,
    для менеджеров только свое,
    для пользователей - только активные.
    """
    if current_user.role == UserRole.USER and not cafe.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Кафе не найдено')

    if current_user.role == UserRole.MANAGER and current_user.cafe_id != cafe_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Менеджер может просматривать только своё кафе',
        )

    return cafe


@router.post(
    '',
    response_model=CafeInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Создание нового кафе',
)
async def create_cafe(
    cafe_create: CafeCreate,
    _: AdminUser,
    session: DBSession,
) -> Cafe:
    """Создает новое кафе.

    Только для администраторов.
    """
    return await cafe_crud.create(cafe_create, session)


@router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Обновление информации о кафе по его ID',
)
async def update_cafe(
    cafe_id: uuid.UUID,
    cafe_update: CafeUpdate,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> Cafe:
    """Обновление информации о кафе по его ID.

    Администратор может обновлять любое кафе,
    менеджер только своё кафе.
    """
    require_manager_cafe_access(current_user, cafe_id)
    return await cafe_crud.update(cafe, cafe_update, session, redis)


@router.delete(
    '/{cafe_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Удаление кафе по его ID (мягкое удаление)',
    include_in_schema=False,
)
async def delete_cafe(
    cafe_id: uuid.UUID,
    _: AdminUser,
    session: DBSession,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> None:
    """Мягкое удаление кафе (установка is_active=False).

    Только для администраторов.
    """
    await cafe_crud.soft_delete(cafe, session)
