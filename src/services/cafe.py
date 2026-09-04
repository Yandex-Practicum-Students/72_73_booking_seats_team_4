import uuid
from typing import Protocol

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.cafe import cafe_crud
from exceptions.cafe import (
    ManagerNotFoundError,
    ManagerRoleError,
)
from exceptions.common import EntityNotFoundError, PermissionDeniedError
from models.cafe import Cafe
from models.user import User, UserRole
from schemas.cafe import CafeCreate, CafeUpdate
from services.media import get_media_or_raise

from core.redis import redis_dep


class CafeReader(Protocol):
    """Минимальный контракт чтения кафе для бизнес-логики."""

    async def get(
        self,
        obj_id: uuid.UUID,
        session: AsyncSession,
    ) -> Cafe | None:
        """Возвращает кафе по идентификатору."""
        ...


async def get_cafe_or_raise(
    cafe_id: uuid.UUID,
    session: AsyncSession,
    cafe_reader: CafeReader,
) -> Cafe:
    """Возвращает кафе или сообщает, что оно не найдено."""
    logger.info('Проверка существования кафе: cafe_id={}', cafe_id)
    cafe = await cafe_reader.get(cafe_id, session)
    if cafe is None:
        logger.warning('Кафе не найдено: cafe_id={}', cafe_id)
        raise EntityNotFoundError('Кафе не найдено')
    logger.info('Кафе найдено: cafe_id={}', cafe_id)
    return cafe


async def ensure_cafes_exist(
    cafe_ids: list[uuid.UUID],
    session: AsyncSession,
    cafe_reader: CafeReader = cafe_crud,
) -> None:
    """Проверяет существование всех кафе из списка."""
    for cafe_id in cafe_ids:
        if await cafe_reader.get(cafe_id, session) is None:
            logger.warning('Кафе не найдено: cafe_id={}', cafe_id)
            raise EntityNotFoundError('Кафе не найдено')


def ensure_manager_cafe_access(user: User, cafe_id: uuid.UUID) -> None:
    """Не позволяет менеджеру управлять чужим кафе."""
    if user.role == UserRole.MANAGER and user.cafe_id != cafe_id:
        logger.warning('Доступ запрещён менеджеру: user_id={}, cafe_id={}', user.id, cafe_id)
        raise PermissionDeniedError('Менеджер может управлять только своим кафе')
    logger.info('Доступ разрешён: user_id={}, cafe_id={}', user.id, cafe_id)


def ensure_manager_cafes_access(
    user: User,
    cafe_ids: list[uuid.UUID],
) -> None:
    """Не позволяет менеджеру управлять ресурсами других кафе."""
    if user.role == UserRole.MANAGER and not set(cafe_ids).issubset({user.cafe_id}):
        logger.warning('Доступ запрещён менеджеру: user_id={}', user.id)
        raise PermissionDeniedError('Менеджер может управлять только своим кафе')
    logger.info('Доступ разрешён: user_id={}', user.id)


async def get_manager_cafes(
    current_user: User,
    session: AsyncSession,
    cafe_reader: CafeReader,
) -> list[Cafe]:
    """Возвращает кафе менеджера или пустой список."""
    if current_user.role != UserRole.MANAGER:
        raise PermissionDeniedError('Только для менеджеров')

    if current_user.cafe_id is None:
        logger.warning('Менеджер не привязан к кафе: user_id={}', current_user.id)
        return []

    cafe = await cafe_reader.get(current_user.cafe_id, session)
    if cafe is None:
        logger.warning('Кафе менеджера не найдено: cafe_id={}', current_user.cafe_id)
        return []

    logger.info('Кафе менеджера найдено: cafe_id={}', current_user.cafe_id)
    return [cafe]


def normalize_managers(cafe: Cafe) -> None:
    """Приводит managers к списку."""
    if cafe.managers is None:
        cafe.managers = []
    elif not isinstance(cafe.managers, list):
        cafe.managers = list(cafe.managers)


async def sync_managers(
    cafe: Cafe,
    manager_ids: list[uuid.UUID] | None,
    session: AsyncSession,
) -> None:
    """Синхронизирует менеджеров кафе: обновляет cafe_id и нормализует список."""
    if manager_ids is not None:
        await set_managers(cafe, manager_ids, session)
        await session.refresh(cafe, attribute_names=['managers'])
        normalize_managers(cafe)


async def ensure_managers_exist_and_role(
    manager_ids: list[uuid.UUID],
    session: AsyncSession,
) -> None:
    """Проверяет, что все добавляемые пользователи существуют и являются менеджерами."""
    result = await session.execute(
        select(User).where(User.id.in_(manager_ids)),
    )
    managers = result.scalars().all()

    found_ids = {user.id for user in managers}
    requested_ids = set(manager_ids)

    if missing := requested_ids - found_ids:
        raise ManagerNotFoundError(
            f'Менеджеры не найдены: {", ".join(map(str, sorted(missing)))}',
        )

    for manager in managers:
        if manager.role != UserRole.MANAGER:
            raise ManagerRoleError(
                f'Пользователь {manager.username} не является менеджером',
            )


async def set_managers(
    cafe: Cafe,
    manager_ids: list[uuid.UUID] | None,
    session: AsyncSession,
) -> None:
    """Устанавливает список менеджеров кафе.

    - Если менеджер был в другом кафе — переназначает его cafe_id
    - Если менеджер удалён из списка — убирает cafe_id
    """
    manager_ids = manager_ids or []
    current_ids = {manager.id for manager in cafe.managers}
    new_ids = set(manager_ids)

    to_add = new_ids - current_ids
    to_remove = current_ids - new_ids

    if to_remove:
        result = await session.execute(
            select(User).where(User.id.in_(list(to_remove))),
        )
        for manager in result.scalars().all():
            logger.info('Убираем менеджера {} из кафе {}', manager.username, cafe.id)
            manager.cafe_id = None
            session.add(manager)

    if to_add:
        result = await session.execute(
            select(User).where(User.id.in_(list(to_add))),
        )
        managers = result.scalars().all()
        for manager in managers:
            if manager.cafe_id is not None and manager.cafe_id != cafe.id:
                logger.info(
                    'Переназначаем менеджера {} из кафе {} в кафе {}',
                    manager.username,
                    manager.cafe_id,
                    cafe.id,
                )
            manager.cafe_id = cafe.id
            session.add(manager)

    if manager_ids:
        result = await session.execute(
            select(User).where(User.id.in_(manager_ids)),
        )
        cafe.managers = result.scalars().all()
    else:
        cafe.managers = []


async def create_cafe(
    cafe_create: CafeCreate,
    session: AsyncSession,
    redis: redis_dep,
) -> Cafe:
    """Проверяет связи и создаёт кафе через слой хранения."""
    logger.info('Создание нового кафе: name={}, address={}', cafe_create.name, cafe_create.address)
    if cafe_create.photo_id is not None:
        await get_media_or_raise(cafe_create.photo_id, session, check_file=False)
    if cafe_create.managers_id:
        await ensure_managers_exist_and_role(cafe_create.managers_id, session)

    created = await cafe_crud.create(cafe_create, session, redis)
    cafe = await cafe_crud.get(created.id, session)
    if cafe is None:
        raise EntityNotFoundError('Созданное кафе не найдено')

    await sync_managers(cafe, cafe_create.managers_id, session)
    await session.flush()
    logger.success('Кафе успешно создано: cafe_id={}, name={}', cafe.id, cafe.name)
    return cafe


async def update_cafe(
    cafe: Cafe,
    cafe_update: CafeUpdate,
    session: AsyncSession,
    redis: redis_dep,
) -> Cafe:
    """Проверяет связи и обновляет кафе через слой хранения."""
    logger.info('Обновление кафе: id={}, name={}', cafe.id, cafe.name)
    update_data = cafe_update.model_dump(exclude_unset=True)
    managers_were_provided = 'managers_id' in update_data
    managers_id = update_data.pop('managers_id', None)

    if 'photo_id' in update_data and update_data['photo_id'] is not None:
        await get_media_or_raise(update_data['photo_id'], session, check_file=False)
    if managers_id:
        await ensure_managers_exist_and_role(managers_id, session)

    if update_data:
        await cafe_crud.update(
            cafe,
            CafeUpdate(**update_data),
            session,
            redis,
        )
        await session.refresh(cafe, attribute_names=['managers'])

    if managers_were_provided:
        await sync_managers(cafe, managers_id, session)
        await session.flush()

    logger.success('Кафе обновлено: id={}, name={}', cafe.id, cafe.name)
    return cafe
