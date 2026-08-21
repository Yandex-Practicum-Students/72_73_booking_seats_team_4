import uuid

from fastapi import HTTPException, status

from api.dependencies.permissions import StaffUser
from crud.cafe import cafe_crud
from crud.slot import slot_crud
from models.cafe import Cafe
from models.slots import Slot
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


async def get_slot_or_404(
    slot_id: uuid.UUID,
    session: DBSession,
) -> Slot:
    """Возвращает слот или выбрасывает 404."""
    slot = await slot_crud.get(slot_id, session)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Слот не найден',
        )
    return slot


async def get_slot_in_cafe(
    cafe_id: uuid.UUID,
    slot_id: uuid.UUID,
    session: DBSession,
) -> Slot:
    """Возвращает слот, принадлежащий кафе, или выбрасывает 404.

    Проверяет:
    1. Существует ли кафе
    2. Существует ли слот
    3. Принадлежит ли слот этому кафе
    """
    await get_cafe_or_404(cafe_id, session)
    slot = await get_slot_or_404(slot_id, session)

    if slot.cafe_id != cafe_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Слот не найден в этом кафе',
        )

    return slot


async def check_manager_cafe_access(
    current_user: StaffUser,
    cafe_id: uuid.UUID,
) -> None:
    """Проверяет, что менеджер имеет доступ к указанному кафе."""
    if current_user.role == UserRole.MANAGER and current_user.cafe_id != cafe_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Менеджер может управлять только своим кафе',
        )
