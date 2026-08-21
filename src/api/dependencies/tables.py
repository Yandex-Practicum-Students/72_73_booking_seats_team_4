import uuid

from fastapi import HTTPException, status
from loguru import logger

from api.dependencies.permissions import StaffUser
from crud.cafe import cafe_crud
from crud.table import table_crud
from models.cafe import Cafe
from models.table import Table
from models.user import UserRole

from core.db import DBSession


async def get_cafe_or_404(
    cafe_id: uuid.UUID,
    session: DBSession,
) -> Cafe:
    """Возвращает кафе или выбрасывает 404."""
    logger.info('Проверка существования кафе: cafe_id={}', cafe_id)
    cafe = await cafe_crud.get(cafe_id, session)
    if cafe is None:
        logger.warning('Кафе не найдено: cafe_id={}', cafe_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кафе не найдено',
        )
    logger.info('Кафе найдено: cafe_id={}', cafe_id)
    return cafe


async def get_table_or_404(
    table_id: uuid.UUID,
    session: DBSession,
) -> Table:
    """Возвращает стол или выбрасывает 404."""
    logger.info('Проверка существования стола: table_id={}', table_id)
    table = await table_crud.get(table_id, session)
    if table is None:
        logger.warning('Стол не найден: table_id={}', table_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Стол не найден',
        )
    logger.info('Стол найден: table_id={}', table_id)
    return table


async def get_table_in_cafe(
    cafe_id: uuid.UUID,
    table_id: uuid.UUID,
    session: DBSession,
) -> Table:
    """Возвращает стол, принадлежащий кафе, или выбрасывает 404.

    Проверяет:
    1. Существует ли кафе
    2. Существует ли стол
    3. Принадлежит ли стол этому кафе
    """
    logger.info('Проверка стола в кафе: cafe_id={}, table_id={}', cafe_id, table_id)
    await get_cafe_or_404(cafe_id, session)
    table = await get_table_or_404(table_id, session)

    if table.cafe_id != cafe_id:
        logger.warning('Стол не принадлежит кафе: cafe_id={}, table_id={}', cafe_id, table_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Стол не найден в этом кафе',
        )
    logger.info('Стол принадлежит кафе: cafe_id={}, table_id={}', cafe_id, table_id)
    return table


def require_manager_cafe_access(user: StaffUser, cafe_id: uuid.UUID) -> None:
    """Проверяет, что менеджер имеет доступ к указанному кафе.

    Для администратора проверка не выполняется.
    """
    if user.role == UserRole.MANAGER and user.cafe_id != cafe_id:
        logger.warning('Доступ запрещён менеджеру: user_id={}, cafe_id={}', user.id, cafe_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Менеджер может управлять только своим кафе',
        )
    logger.info('Доступ разрешён: user_id={}, cafe_id={}', user.id, cafe_id)
