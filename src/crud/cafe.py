import uuid
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.cafe import Cafe
from schemas.cafe import CafeCreate, CafeInfo, CafeUpdate
from services.cafe import ensure_managers_exist_and_role, normalize_managers, sync_managers

from core.core_dependencies import redis_dep


class ManagerNotFoundError(ValueError):
    """Ошибка: менеджер не найден."""


class ManagerRoleError(ValueError):
    """Ошибка: пользователь не является менеджером."""


class ManagerAlreadyAssignedError(ValueError):
    """Ошибка: менеджер уже привязан к другому кафе."""


class CafeCRUD(CRUDBase[Cafe, CafeCreate, CafeUpdate]):
    """CRUD-операции для кафе и связанных менеджеров."""

    def __init__(self) -> None:
        """Настраивает модель кафе и соответствие поля менеджеров."""
        super().__init__(Cafe, CafeInfo, rel_map={'managers_id': 'managers'})

    async def get(self, obj_id: uuid.UUID, session: AsyncSession) -> Cafe | None:
        """Возвращает кафе вместе со списком менеджеров."""
        logger.info('Получение кафе по ID: {}', obj_id)
        cafe = await super().get(obj_id, session, options=[selectinload(Cafe.managers)])
        if cafe:
            normalize_managers(cafe)
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
        logger.info('Получение всех кафе: show_active={}', show_active)

        cafes = await super().get_all(
            session=session,
            is_active=show_active,
            options=[selectinload(Cafe.managers)],
        )

        for cafe in cafes:
            normalize_managers(cafe)

        logger.success('Найдено {} кафе', len(cafes))
        return cafes

    async def create(
            self,
            obj_in: CafeCreate,
            session: AsyncSession,
            redis: redis_dep,
    ) -> Cafe:
        """Создаёт новое кафе.

        Обновляет поле cafe_id менеджера с помощью sync_managers()
        """
        logger.info('Создание нового кафе: name={}, address={}', obj_in.name, obj_in.address)
        if obj_in.managers_id:
            await ensure_managers_exist_and_role(obj_in.managers_id, session)
        cafe_schema = await super().create(obj_in, session, redis)
        cafe = await self.get(cafe_schema.id, session)
        await sync_managers(cafe, obj_in.managers_id, session)

        logger.success('Кафе успешно создано: cafe_id={}, name={}', cafe.id, cafe.name)
        return cafe

    async def update(
            self,
            db_obj: Cafe,
            obj_in: CafeUpdate,
            session: AsyncSession,
            redis: redis_dep,
    ) -> Cafe:
        """Обновляет кафе.

        Обновляет поле cafe_id менеджера с помощью sync_managers()
        """
        logger.info('Обновление кафе: id={}, name={}', db_obj.id, db_obj.name)

        update_data = obj_in.model_dump(exclude_unset=True)
        managers_id = update_data.pop('managers_id', None)

        if managers_id:
            await ensure_managers_exist_and_role(managers_id, session)

        if update_data:
            temp_obj = CafeUpdate(**update_data)
            await super().update(db_obj, temp_obj, session, redis)
            await session.refresh(db_obj, attribute_names=['managers'])

        await sync_managers(db_obj, managers_id, session)

        logger.success('Кафе обновлено: id={}, name={}', db_obj.id, db_obj.name)
        return db_obj


cafe_crud = CafeCRUD()
