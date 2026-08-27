import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.cafe import cafe_crud
from crud.dish import dish_crud
from models.dish import Dish
from models.user import User, UserRole
from services.errors import EntityNotFoundError, PermissionDeniedError


async def get_dish_or_raise(
    dish_id: uuid.UUID,
    session: AsyncSession,
) -> Dish:
    """Возвращает блюдо или сообщает, что оно не найдено."""
    logger.info('Проверка существования блюда: dish_id={}', dish_id)
    dish = await dish_crud.get(dish_id, session)
    if dish is None:
        logger.warning('Блюдо не найдено: dish_id={}', dish_id)
        raise EntityNotFoundError('Блюдо не найдено')
    logger.info('Блюдо найдено: dish_id={}', dish_id)
    return dish


async def ensure_cafes_exist(
    cafe_ids: list[uuid.UUID],
    session: AsyncSession,
) -> None:
    """Проверяет существование всех кафе из списка."""
    for cafe_id in cafe_ids:
        if await cafe_crud.get(cafe_id, session) is None:
            logger.warning('Кафе не найдено: cafe_id={}', cafe_id)
            raise EntityNotFoundError('Кафе не найдено')


def ensure_manager_cafe_access(
    user: User,
    cafe_ids: list[uuid.UUID],
) -> None:
    """Не позволяет менеджеру управлять блюдами других кафе."""
    if user.role == UserRole.MANAGER and not set(cafe_ids).issubset({user.cafe_id}):
        logger.warning('Доступ запрещён менеджеру: user_id={}', user.id)
        raise PermissionDeniedError('Менеджер может управлять только своим кафе')
    logger.info('Доступ разрешён: user_id={}', user.id)
