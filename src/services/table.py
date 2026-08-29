import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.cafe import cafe_crud
from crud.table import table_crud
from models.table import Table
from services.cafe import get_cafe_or_raise
from services.errors import EntityNotFoundError


async def get_table_in_cafe_or_raise(
    cafe_id: uuid.UUID,
    table_id: uuid.UUID,
    session: AsyncSession,
) -> Table:
    """Возвращает стол указанного кафе или сообщает, что он не найден."""
    logger.info('Проверка стола в кафе: cafe_id={}, table_id={}', cafe_id, table_id)
    try:
        cafe = await get_cafe_or_raise(cafe_id, session, cafe_crud)
    except EntityNotFoundError:
        logger.warning('Кафе не найдено: cafe_id={}', cafe_id)
        raise EntityNotFoundError(f'Кафе с ID "{cafe_id}" не найдено')
    table = await table_crud.get_by_cafe_and_id(cafe_id, table_id, session)
    if table is None:
        logger.warning('Стол не принадлежит кафе: cafe_id={}, table_id={}', cafe_id, table_id)
        raise EntityNotFoundError(f'Стол не найден в кафе "{cafe_id}"')
    logger.info('Стол принадлежит кафе: cafe_id={}, table_id={}', cafe_id, table_id)
    return table
