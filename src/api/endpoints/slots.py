import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.permissions import CurrentUser, StaffUser
from api.dependencies.slots import (
    check_manager_cafe_access,
    get_cafe_or_404,
    get_slot_in_cafe,
)
from api.responses import error_responses
from crud.slot import slot_crud
from models.cafe import Cafe
from models.slots import Slot
from models.user import UserRole
from schemas.slots import TimeSlotCreate, TimeSlotInfo, TimeSlotUpdate

from core.core_dependencies import redis_dep
from core.db import DBSession

_COMMON_404 = (status.HTTP_404_NOT_FOUND,)
_COMMON_AUTH = (
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
)
_COMMON_VALIDATION = (status.HTTP_422_UNPROCESSABLE_CONTENT,)

GET_RESPONSES = _COMMON_AUTH + _COMMON_404 + _COMMON_VALIDATION
POST_RESPONSES = (status.HTTP_400_BAD_REQUEST,) + GET_RESPONSES
PATCH_RESPONSES = (status.HTTP_400_BAD_REQUEST,) + GET_RESPONSES
DELETE_RESPONSES = _COMMON_AUTH + _COMMON_404 + _COMMON_VALIDATION

router = APIRouter()


@router.get(
    '',
    response_model=list[TimeSlotInfo],
    responses=error_responses(*GET_RESPONSES),
    summary='Список временных слотов в кафе',
)
async def get_slots_by_cafe(
    cafe_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    show_active: Optional[bool] = Query(None),
    _cafe: Cafe = Depends(get_cafe_or_404),
) -> list[Slot]:
    """Получение списка доступных для бронирования временных слотов в кафе.

    Администратор видит все слоты (учитывая show_active),
    менеджер и пользователь — только активные.
    """
    if current_user.role != UserRole.ADMIN:
        show_active = True
    return await slot_crud.get_by_cafe(
        cafe_id=cafe_id,
        session=session,
        show_active=show_active,
    )


@router.post(
    '',
    response_model=TimeSlotInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(*POST_RESPONSES),
    summary='Новый временной слот в кафе',
)
async def create_slot(
    cafe_id: uuid.UUID,
    slot_create: TimeSlotCreate,
    current_user: StaffUser,
    session: DBSession,
    _cafe: Cafe = Depends(get_cafe_or_404),
) -> Slot:
    """Создает новый временной слот в кафе.

    Менеджер создает слоты только в своём кафе.
    """
    await check_manager_cafe_access(current_user, cafe_id)
    return await slot_crud.create_with_cafe(cafe_id, slot_create, session)


@router.get(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    responses=error_responses(*GET_RESPONSES),
    summary='Информация о временном слоте в кафе по его ID',
)
async def get_slot_by_id(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    _slot: Slot = Depends(get_slot_in_cafe),
) -> Slot:
    """Получение информации о временном слоте в кафе по его ID.

    Для администраторов и менеджеров — все слоты,
    для пользователей — только активные.
    """
    await check_manager_cafe_access(current_user, cafe_id)

    if current_user.role == UserRole.USER and not _slot.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Слот не найден',
        )

    return _slot


@router.patch(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    responses=error_responses(*PATCH_RESPONSES),
    summary='Обновление информации о временном слоте в кафе по его ID',
)
async def update_slot(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    slot_update: TimeSlotUpdate,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
    _slot: Slot = Depends(get_slot_in_cafe),
) -> Slot:
    """Обновление информации о временном слоте в кафе по его ID.

    Менеджер обновляет слоты только в своём кафе.
    """
    await check_manager_cafe_access(current_user, cafe_id)
    return await slot_crud.update(_slot, slot_update, session, redis)


@router.delete(
    '/{slot_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(*DELETE_RESPONSES),
    summary='Удаление временного слота по его ID (мягкое удаление)',
)
async def delete_slot(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    current_user: StaffUser,
    session: DBSession,
    _slot: Slot = Depends(get_slot_in_cafe),
) -> None:
    """Мягкое удаление временного слота в кафе (установка is_active=False).

    Менеджер удаляет слоты только в своём кафе.
    """
    await check_manager_cafe_access(current_user, cafe_id)
    await slot_crud.soft_delete(_slot, session)
