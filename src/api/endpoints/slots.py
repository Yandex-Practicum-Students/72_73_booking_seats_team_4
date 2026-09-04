import uuid

from fastapi import APIRouter, Depends

from api.dependencies.cafe import get_cafe_or_404
from api.dependencies.filters import Boolean, filter_user_role_manager_for_cafe_id, resolve_show_active
from api.dependencies.permissions import CurrentUser, StaffUser, ensure_active_resource_visible
from api.dependencies.slots import get_slot_in_cafe
from api.responses import error_responses
from api.responses.statuses import CREATED, RESOURCE_CREATE_WITH_PARENT, RESOURCE_DETAIL, RESOURCE_UPDATE
from crud.slot import slot_crud
from models.cafe import Cafe
from models.slots import Slot
from schemas.slots import TimeSlotCreate, TimeSlotInfo, TimeSlotUpdate
from services.cafe import ensure_manager_cafe_access

from core.db import DBSession
from core.redis import redis_dep

router = APIRouter()


@router.get(
    '',
    response_model=list[TimeSlotInfo],
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Список временных слотов в кафе',
)
async def get_slots_by_cafe(
    cafe_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    show_active: Boolean = None,
    _cafe: Cafe = Depends(get_cafe_or_404),
) -> list[Slot]:
    """Получение списка доступных для бронирования временных слотов в кафе.

    Администратор видит все слоты (учитывая show_active),
    менеджер и пользователь — только активные.
    """
    show_active = resolve_show_active(current_user, show_active)
    cafe_id = filter_user_role_manager_for_cafe_id(current_user, cafe_id)
    return await slot_crud.get_by_cafe(
        cafe_id=cafe_id,
        session=session,
        show_active=show_active,
    )


@router.post(
    '',
    response_model=TimeSlotInfo,
    status_code=CREATED,
    responses=error_responses(*RESOURCE_CREATE_WITH_PARENT),
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
    ensure_manager_cafe_access(current_user, cafe_id)
    return await slot_crud.create_with_cafe(cafe_id, slot_create, session)


@router.get(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    responses=error_responses(*RESOURCE_DETAIL),
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
    ensure_manager_cafe_access(current_user, cafe_id)

    ensure_active_resource_visible(current_user, _slot, 'Слот не найден')

    return _slot


@router.patch(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    responses=error_responses(*RESOURCE_UPDATE),
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
    ensure_manager_cafe_access(current_user, cafe_id)
    return await slot_crud.update(_slot, slot_update, session, redis)
