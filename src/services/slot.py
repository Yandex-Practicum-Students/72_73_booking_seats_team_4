import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.slot import slot_crud
from models.slots import Slot
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
