import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from models.slots import Slot
from schemas.slots import TimeSlotCreate, TimeSlotInfo, TimeSlotUpdate

from core.db import get_session

router = APIRouter()


@router.get(
    '',
    response_model=list[TimeSlotInfo],
    summary='Список временных слотов в кафе',
)
async def get_tables_by_cafe(
    session: AsyncSession = Depends(get_session),
) -> list[Slot]:
    """Получение списка доступных для бронирования временных слотов в кафе.

    Для администраторов и менеджеров - все столы (с возможностью выбора),
    для пользователей - только активные.
    """


@router.post(
    '',
    response_model=TimeSlotInfo,
    summary='овый временной слот в кафе',
)
async def create_cafe(
    slot_create: TimeSlotCreate,
    session: AsyncSession = Depends(get_session),
) -> Slot:
    """Создает новый временной слот в кафе.

    Только для администраторов и менеджеров.
    """


@router.patch(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    summary='Обновление информации о временом слоте в кафе по его ID',
)
async def update_table(
    slot_id: uuid.UUID,
    slot_update: TimeSlotUpdate,
    session: AsyncSession = Depends(get_session),
) -> Slot:
    """Обновление информации о временом слоте в кафе по его ID.

    Только для администраторов и менеджеров.
    """
