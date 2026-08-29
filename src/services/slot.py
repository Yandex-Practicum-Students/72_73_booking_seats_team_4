import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.slot import slot_crud
from models.slots import Slot
from services.cafe import CafeReader, get_cafe_or_raise
from services.errors import EntityNotFoundError


async def get_slot_in_cafe_or_raise(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    session: AsyncSession,
    cafe_reader: CafeReader,
) -> Slot:
    """Возвращает слот указанного кафе или сообщает, что он не найден."""
    await get_cafe_or_raise(cafe_id, session, cafe_reader)
    slot = await slot_crud.get_by_cafe_and_id(cafe_id, slot_id, session)
    if slot is None:
        logger.warning('Слот не принадлежит кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
        raise EntityNotFoundError('Слот не найден в этом кафе')
    logger.info('Слот принадлежит кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
    return slot
