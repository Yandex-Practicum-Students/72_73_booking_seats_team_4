import uuid

from fastapi import HTTPException, status
from loguru import logger

from api.dependencies.permissions import StaffUser
from crud.dish import dish_crud
from models.dish import Dish
from models.user import UserRole

from core.db import DBSession


async def get_dish_or_404(
    dish_id: uuid.UUID,
    session: DBSession,
) -> Dish:
    """Возвращает блюдо или выбрасывает 404."""
    logger.info('Проверка существования блюда: dish_id={}', dish_id)
    dish = await dish_crud.get(dish_id, session)
    if dish is None:
        logger.warning('Блюдо не найдено: dish_id={}', dish_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Блюдо не найдено',
        )
    logger.info('Блюдо найдено: dish_id={}', dish_id)
    return dish


def require_manager_cafe_access_for_dish(
    user: StaffUser,
    cafes_id: list,
) -> None:
    """Проверяет, что менеджер имеет доступ к указанным кафе блюда.

    Для администратора проверка не выполняется.
    """
    if user.role == UserRole.MANAGER:
        allowed_ids = {user.cafe_id}
        if not set(cafes_id).issubset(allowed_ids):
            logger.warning('Доступ запрещён менеджеру: user_id={}', user.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Менеджер может управлять только своим кафе',
            )
    logger.info('Доступ разрешён: user_id={}', user.id)
