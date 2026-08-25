import uuid

from fastapi import HTTPException, status
from loguru import logger

from api.dependencies.permissions import StaffUser
from api.dependencies.tables import get_cafe_or_404
from crud.slot import slot_crud
from models.slots import Slot
from models.user import UserRole

from core.db import DBSession


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
    logger.info('Проверка слота в кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
    slot = await slot_crud.get_by_cafe_and_id(cafe_id, slot_id, session)

    if slot is None:
        logger.warning('Слот не принадлежит кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Слот не найден в этом кафе',
        )
    logger.info('Слот принадлежит кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
    return slot


async def check_manager_cafe_access(
    current_user: StaffUser,
    cafe_id: uuid.UUID,
) -> None:
    """Проверяет, что менеджер имеет доступ к указанному кафе."""
    if current_user.role == UserRole.MANAGER and current_user.cafe_id != cafe_id:
        logger.warning(
            'Доступ запрещён менеджеру: user_id={}, cafe_id={}',
            current_user.id,
            cafe_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Менеджер может управлять только своим кафе',
        )
    logger.info('Доступ разрешён: user_id={}, cafe_id={}', current_user.id, cafe_id)
