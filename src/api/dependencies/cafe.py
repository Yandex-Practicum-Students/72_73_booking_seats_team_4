import uuid

from crud.cafe import cafe_crud
from models.cafe import Cafe
from services.cafe import get_cafe_or_raise

from core.db import DBSession


async def get_cafe_or_404(
    cafe_id: uuid.UUID,
    session: DBSession,
) -> Cafe:
    """FastAPI-зависимость для получения существующего кафе."""
    return await get_cafe_or_raise(cafe_id, session, cafe_crud)
