import uuid

from models.slots import Slot
from services.slot import get_slot_in_cafe_or_raise

from core.db import DBSession


async def get_slot_in_cafe(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    session: DBSession,
) -> Slot:
    """FastAPI-зависимость для получения слота указанного кафе."""
    return await get_slot_in_cafe_or_raise(cafe_id, slot_id, session)
