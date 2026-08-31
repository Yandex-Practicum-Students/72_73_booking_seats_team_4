import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.action import action_crud
from models.action import Action
from models.user import User
from schemas.action import ActionCreate, ActionUpdate
from services.cafe import ensure_cafes_exist, ensure_manager_cafes_access
from services.errors import EntityNotFoundError

from core.core_dependencies import redis_dep


async def get_action_or_raise(
    action_id: uuid.UUID,
    session: AsyncSession,
) -> Action:
    """Возвращает акцию или сообщает, что она не найдена."""
    logger.info('Проверка существования акции: action_id={}', action_id)
    action = await action_crud.get(action_id, session)
    if action is None:
        logger.warning('Акция не найдена: action_id={}', action_id)
        raise EntityNotFoundError('Акция не найдена')
    logger.info('Акция найдена: action_id={}', action_id)
    return action


async def create_action(
    action_create: ActionCreate,
    current_user: User,
    session: AsyncSession,
    redis: redis_dep,
) -> Action:
    """Проверяет права и связи, затем создаёт акцию."""
    ensure_manager_cafes_access(current_user, action_create.cafes_id)
    await ensure_cafes_exist(action_create.cafes_id, session)
    return await action_crud.create(action_create, session, redis)


async def update_action(
    action: Action,
    action_update: ActionUpdate,
    current_user: User,
    session: AsyncSession,
    redis: redis_dep,
) -> Action:
    """Проверяет старые и новые связи, затем обновляет акцию."""
    current_cafe_ids = [cafe.id for cafe in action.cafes]
    ensure_manager_cafes_access(current_user, current_cafe_ids)
    new_cafe_ids = (
        action_update.cafes_id
        if action_update.cafes_id is not None
        else current_cafe_ids
    )
    ensure_manager_cafes_access(current_user, new_cafe_ids)
    await ensure_cafes_exist(new_cafe_ids, session)
    return await action_crud.update(action, action_update, session, redis)
