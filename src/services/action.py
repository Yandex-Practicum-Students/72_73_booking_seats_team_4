import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.action import action_crud
from crud.cafe import cafe_crud
from models.action import Action
from models.user import User, UserRole
from services.errors import EntityNotFoundError, PermissionDeniedError


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
    """Не позволяет менеджеру управлять акциями других кафе."""
    if user.role == UserRole.MANAGER and not set(cafe_ids).issubset({user.cafe_id}):
        logger.warning('Доступ запрещён менеджеру: user_id={}', user.id)
        raise PermissionDeniedError('Менеджер может управлять только своим кафе')
    logger.info('Доступ разрешён: user_id={}', user.id)
