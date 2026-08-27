import uuid

from models.table import Table
from services.table import get_table_in_cafe_or_raise

from core.db import DBSession


async def get_table_in_cafe(
    cafe_id: uuid.UUID,
    table_id: uuid.UUID,
    session: DBSession,
) -> Table:
    """FastAPI-зависимость для получения стола указанного кафе."""
    return await get_table_in_cafe_or_raise(cafe_id, table_id, session)
