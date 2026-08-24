import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.cafe import Cafe
from models.user import User, UserRole


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

    found_ids = {str(u.id) for u in managers}
    requested_ids = {str(manager_id) for manager_id in manager_ids}

    if missing := requested_ids - found_ids:
        raise ValueError(f'Пользователи не найдены: {missing}')

    for manager in managers:
        if manager.role != UserRole.MANAGER:
            raise ValueError(
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
    current_ids = {str(m.id) for m in cafe.managers}
    new_ids = {str(manager_id) for manager_id in manager_ids}

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
                logger.info('Переназначаем менеджера {} из кафе {} в кафе {}',
                            manager.username, manager.cafe_id, cafe.id)
            manager.cafe_id = cafe.id
            session.add(manager)

    if manager_ids:
        result = await session.execute(
            select(User).where(User.id.in_(manager_ids)),
        )
        cafe.managers = list(result.scalars().all())
    else:
        cafe.managers = []
