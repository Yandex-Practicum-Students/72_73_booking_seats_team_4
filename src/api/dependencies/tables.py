import uuid

from fastapi import HTTPException, status

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
    cafe = await cafe_crud.get(cafe_id, session)
    if cafe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кафе не найдено',
        )
    return cafe


async def get_table_or_404(
    table_id: uuid.UUID,
    session: DBSession,
) -> Table:
    """Возвращает стол или выбрасывает 404."""
    table = await table_crud.get(table_id, session)
    if table is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Стол не найден',
        )
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
    await get_cafe_or_404(cafe_id, session)
    table = await get_table_or_404(table_id, session)

    if table.cafe_id != cafe_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Стол не найден в этом кафе',
        )

    return table


def require_manager_cafe_access(user: StaffUser, cafe_id: uuid.UUID) -> None:
    """Проверяет, что менеджер имеет доступ к указанному кафе.

    Для администратора проверка не выполняется.
    """
    if user.role == UserRole.MANAGER and user.cafe_id != cafe_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Менеджер может управлять только своим кафе',
        )
