import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.table import table_crud
from models.table import Table
from services.cafe_resource import get_cafe_resource_or_raise


async def get_table_in_cafe_or_raise(
    cafe_id: uuid.UUID,
    table_id: uuid.UUID,
    session: AsyncSession,
) -> Table:
    """Возвращает стол указанного кафе или сообщает, что он не найден."""
    logger.info('Проверка стола в кафе: cafe_id={}, table_id={}', cafe_id, table_id)
    table = await get_cafe_resource_or_raise(
        cafe_id,
        table_id,
        session,
        table_crud,
        'Стол не найден в этом кафе',
    )
    logger.info('Стол принадлежит кафе: cafe_id={}, table_id={}', cafe_id, table_id)
    return table
