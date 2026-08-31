import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.dish import dish_crud
from models.dish import Dish
from models.user import User
from schemas.dish import DishCreate, DishUpdate
from services.cafe import ensure_cafes_exist, ensure_manager_cafes_access
from services.errors import EntityNotFoundError
from services.media import get_media_or_raise

from core.core_dependencies import redis_dep


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


async def create_dish(
    dish_create: DishCreate,
    current_user: User,
    session: AsyncSession,
    redis: redis_dep,
) -> Dish:
    """Проверяет права и связи, затем создаёт блюдо."""
    ensure_manager_cafes_access(current_user, dish_create.cafes_id)
    await ensure_cafes_exist(dish_create.cafes_id, session)
    if dish_create.photo_id is not None:
        await get_media_or_raise(dish_create.photo_id, session, check_file=False)
    return await dish_crud.create(dish_create, session, redis)


async def update_dish(
    dish: Dish,
    dish_update: DishUpdate,
    current_user: User,
    session: AsyncSession,
    redis: redis_dep,
) -> Dish:
    """Проверяет права и связи, затем обновляет блюдо."""
    current_cafe_ids = [cafe.id for cafe in dish.cafes]
    ensure_manager_cafes_access(current_user, current_cafe_ids)
    new_cafe_ids = (
        dish_update.cafes_id
        if dish_update.cafes_id is not None
        else current_cafe_ids
    )
    ensure_manager_cafes_access(current_user, new_cafe_ids)
    await ensure_cafes_exist(new_cafe_ids, session)
    if 'photo_id' in dish_update.model_fields_set and dish_update.photo_id is not None:
        await get_media_or_raise(dish_update.photo_id, session, check_file=False)
    return await dish_crud.update(dish, dish_update, session, redis)
