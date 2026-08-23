import uuid
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.cafe import Cafe
from schemas.cafe import CafeCreate, CafeInfo, CafeUpdate

from models.user import User, UserRole


class CafeCRUD(CRUDBase[Cafe, CafeCreate, CafeUpdate]):
    """CRUD-операции для кафе и связанных менеджеров."""

    def __init__(self) -> None:
        """Настраивает модель кафе и соответствие поля менеджеров."""
        super().__init__(Cafe, CafeInfo, rel_map={'managers_id': 'managers'})

    @staticmethod
    def _normalize_managers(cafe: Cafe) -> None:
        """Приводит managers к списку."""
        if cafe.managers is None:
            cafe.managers = []
        elif not isinstance(cafe.managers, list):
            cafe.managers = list(cafe.managers)

    async def get(self, obj_id: uuid.UUID, session: AsyncSession) -> Cafe | None:
        """Возвращает кафе вместе со списком менеджеров."""
        logger.info('Получение кафе по ID: {}', obj_id)
        cafe = await super().get(obj_id, session, options=[selectinload(Cafe.managers)])
        if cafe:
            self._normalize_managers(cafe)
            logger.success('Кафе найдено: cafe_id={}, name={}', obj_id, cafe.name)
        else:
            logger.warning('Кафе не найдено: cafe_id={}', obj_id)
        return cafe

    async def get_all(
        self,
        session: AsyncSession,
        show_active: Optional[bool] = None,
    ) -> list[Cafe]:
        """Возвращает все кафе вместе со списками менеджеров с фильтрацией по активности."""
        query = select(Cafe)
        if show_active is not None:
            query = query.where(Cafe.is_active == show_active)
        query = query.order_by(Cafe.created_at).options(selectinload(Cafe.managers))
        result = await session.execute(query)
        cafes = list(result.scalars().all())

        for cafe in cafes:
            self._normalize_managers(cafe)

        logger.success('Найдено {} кафе', len(cafes))
        return cafes


    async def create(self, obj_in: CafeCreate, session: AsyncSession) -> Cafe:
        """Создаёт новое кафе.

        managers_id устанавливаем с помощью _set_managers()
        остальные поля - через базовый create()
        """
        logger.info('Создание нового кафе: name={}, address={}', obj_in.name, obj_in.address)
        if obj_in.managers_id:
            await self._ensure_managers_exist_and_role(obj_in.managers_id, session)

        cafe = await super().create(obj_in, session)

        if obj_in.managers_id:
            await self._set_managers(cafe, obj_in.managers_id, session)
            await session.refresh(cafe, attribute_names=['managers'])
            self._normalize_managers(cafe)

        logger.success('Кафе успешно создано: cafe_id={}, name={}', cafe.id, cafe.name)
        return cafe

    async def update(self, db_obj: Cafe, obj_in: CafeUpdate, session: AsyncSession) -> Cafe:
        """Обновляет кафе.

        managers_id обновляем с помощью _set_managers()
        остальные поля - через базовый update()
        """
        logger.info('Обновление кафе: id={}, name={}', db_obj.id, db_obj.name)
        update_data = obj_in.model_dump(exclude_unset=True)

        if 'managers_id' in update_data:
            new_manager_ids = update_data['managers_id'] or []
            if new_manager_ids:
                await self._ensure_managers_exist_and_role(new_manager_ids, session)
            await self._set_managers(db_obj, new_manager_ids, session)
            update_data.pop('managers_id', None)

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        await session.refresh(db_obj, attribute_names=['managers'])
        self._normalize_managers(db_obj)

        logger.success('Кафе обновлено: id={}, name={}', db_obj.id, db_obj.name)
        return db_obj


    async def _ensure_managers_exist_and_role(
                self,
                manager_ids: list[uuid.UUID],
                session: AsyncSession,
        ) -> None:
            """Проверяет, что все пользователи существуют и являются менеджерами."""
            result = await session.execute(
                select(User).where(User.id.in_(manager_ids))
            )
            managers = result.scalars().all()

            found_ids = {str(u.id) for u in managers}
            requested_ids = {str(id) for id in manager_ids}

            if missing := requested_ids - found_ids:
                raise ValueError(f'Пользователи не найдены: {missing}')

            for manager in managers:
                if manager.role != UserRole.MANAGER:
                    raise ValueError(
                        f'Пользователь {manager.username} не является менеджером'
                    )

    async def _set_managers(
            self,
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
        new_ids = {str(id) for id in manager_ids}

        to_add = new_ids - current_ids
        to_remove = current_ids - new_ids

        if to_remove:
            result = await session.execute(
                select(User).where(User.id.in_(list(to_remove)))
            )
            for manager in result.scalars().all():
                logger.info('Убираем менеджера {} из кафе {}', manager.username, cafe.id)
                manager.cafe_id = None
                session.add(manager)

        if to_add:
            result = await session.execute(
                select(User).where(User.id.in_(list(to_add)))
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
                select(User).where(User.id.in_(manager_ids))
            )
            cafe.managers = list(result.scalars().all())
        else:
            cafe.managers = []

cafe_crud = CafeCRUD()
