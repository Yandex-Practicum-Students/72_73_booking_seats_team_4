import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import StaffUser
from crud.cafe import cafe_crud
from crud.slot import slot_crud
from models.slots import Slot
from schemas.slots import TimeSlotCreate, TimeSlotInfo, TimeSlotUpdate

from core.db import get_session

router = APIRouter()


async def _ensure_cafe_exists(cafe_id: uuid.UUID, session: AsyncSession) -> None:
    """Проверяет, что кафе существует, иначе возвращает 404."""
    cafe = await cafe_crud.get(cafe_id, session)
    if cafe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кафе не найдено.',
        )


async def _get_slot_or_404(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    session: AsyncSession,
) -> Slot:
    """Возвращает слот кафе либо 404, если слот не найден или из другого кафе."""
    slot = await slot_crud.get(slot_id, session)
    if slot is None or slot.cafe_id != cafe_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Слот не найден.',
        )
    return slot


@router.get(
    '',
    response_model=list[TimeSlotInfo],
    summary='Список временных слотов в кафе',
)
async def get_slots_by_cafe(
    cafe_id: uuid.UUID,
    show_active: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[Slot]:
    """Получение списка доступных для бронирования временных слотов в кафе.

    Для администраторов и менеджеров - все слоты (с возможностью выбора),
    для пользователей - только активные.
    """
    await _ensure_cafe_exists(cafe_id, session)
    return await slot_crud.get_by_cafe(cafe_id, session, show_active=show_active)


@router.post(
    '',
    response_model=TimeSlotInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Новый временной слот в кафе',
)
async def create_slot(
    cafe_id: uuid.UUID,
    slot_create: TimeSlotCreate,
    _: StaffUser,
    session: AsyncSession = Depends(get_session),
) -> Slot:
    """Создает новый временной слот в кафе.

    Только для администраторов и менеджеров.
    """
    await _ensure_cafe_exists(cafe_id, session)
    return await slot_crud.create(slot_create, session)


@router.get(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    summary='Информация о временном слоте в кафе по его ID',
)
async def get_slot_by_id(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Slot:
    """Получение информации о временном слоте в кафе по его ID."""
    return await _get_slot_or_404(cafe_id, slot_id, session)


@router.patch(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    summary='Обновление информации о временном слоте в кафе по его ID',
)
async def update_slot(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    slot_update: TimeSlotUpdate,
    _: StaffUser,
    session: AsyncSession = Depends(get_session),
) -> Slot:
    """Обновление информации о временном слоте в кафе по его ID.

    Только для администраторов и менеджеров.
    """
    slot = await _get_slot_or_404(cafe_id, slot_id, session)
    return await slot_crud.update(slot, slot_update, session)
