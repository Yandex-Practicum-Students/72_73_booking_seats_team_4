import uuid
from datetime import time

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.slot import slot_crud
from exceptions.slot import SlotOverlapError
from models.slots import Slot
from models.user import User
from schemas.slots import TimeSlotCreate
from services.cafe import ensure_manager_cafe_access
from services.cafe_resource import get_cafe_resource_or_raise


async def get_slot_in_cafe_or_raise(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    session: AsyncSession,
) -> Slot:
    """Возвращает слот указанного кафе или сообщает, что он не найден."""
    slot = await get_cafe_resource_or_raise(
        cafe_id,
        slot_id,
        session,
        slot_crud,
        'Слот не найден в этом кафе',
    )
    logger.info('Слот принадлежит кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
    return slot


async def check_slot_not_overlapping(
    cafe_id: uuid.UUID,
    start_time: time,
    end_time: time,
    session: AsyncSession,
) -> None:
    """Проверяет, что новый слот не пересекается по времени с существующими в кафе."""
    logger.info(
        'Проверка пересечения слота: cafe_id={}, start_time={}, end_time={}',
        cafe_id,
        start_time,
        end_time,
    )
    existing = await session.execute(
        select(Slot).where(
            Slot.cafe_id == cafe_id,
            Slot.is_active.is_(True),
            Slot.start_time < end_time,
            start_time < Slot.end_time,
        ),
    )
    if existing.scalars().first() is not None:
        logger.warning(
            'Обнаружен пересекающийся слот в кафе: cafe_id={}, start_time={}, end_time={}',
            cafe_id,
            start_time,
            end_time,
        )
        raise SlotOverlapError


async def create_slot_in_cafe(
    cafe_id: uuid.UUID,
    slot_create: TimeSlotCreate,
    current_user: User,
    session: AsyncSession,
) -> Slot:
    """Проверяет доступ менеджера и отсутствие пересечений, затем создаёт слот."""
    ensure_manager_cafe_access(current_user, cafe_id)
    await check_slot_not_overlapping(cafe_id, slot_create.start_time, slot_create.end_time, session)
    return await slot_crud.create_with_cafe(cafe_id, slot_create, session)
