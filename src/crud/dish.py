import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.cafe import Cafe
from models.dish import Dish
from schemas.dish import DishCreate, DishInfo, DishUpdate

from core.core_dependencies import redis_dep


class DishAlreadyExistsError(ValueError):
    """Блюдо с таким именем уже существует."""


class DishCRUD(CRUDBase[Dish, DishCreate, DishUpdate]):
    """CRUD-операции для блюд."""

    def __init__(self) -> None:
        """Настраивает модель блюда и связь с кафе."""
        super().__init__(Dish, DishInfo, rel_map={'cafes_id': 'cafes'})

    async def create(
        self,
        obj_in: DishCreate,
        session: AsyncSession,
        redis: redis_dep,
    ) -> Dish:
        """Создаёт блюдо, преобразуя конфликт уникальности имени."""
        try:
            return await super().create(obj_in, session, redis)
        except IntegrityError as error:
            await session.rollback()
            raise DishAlreadyExistsError from error

    async def update(
        self,
        db_obj: Dish,
        obj_in: DishUpdate,
        session: AsyncSession,
        redis: redis_dep,
    ) -> Dish:
        """Обновляет блюдо, преобразуя конфликт уникальности имени."""
        try:
            return await super().update(db_obj, obj_in, session, redis)
        except IntegrityError as error:
            await session.rollback()
            raise DishAlreadyExistsError from error

    async def get(
        self,
        obj_id: uuid.UUID,
        session: AsyncSession,
    ) -> Dish | None:
        """Возвращает блюдо вместе со связанными кафе."""
        logger.info('Получение блюда по ID: {}', obj_id)
        return await super().get(
            obj_id,
            session,
            options=[selectinload(Dish.cafes)],
        )

    async def get_all(
        self,
        session: AsyncSession,
        is_active: bool | None = None,
        cafe_id: uuid.UUID | None = None,
    ) -> list[Dish]:
        """Возвращает все блюда, при необходимости фильтруя по активности и кафе."""
        logger.info('Получение всех блюд: is_active={}, cafe_id={}', is_active, cafe_id)
        query = select(Dish)
        if is_active is not None:
            query = query.where(Dish.is_active == is_active)
        if cafe_id is not None:
            query = query.join(Dish.cafes).where(Cafe.id == cafe_id)
        query = query.options(selectinload(Dish.cafes))
        result = await session.execute(query)
        dishes = result.scalars().all()
        logger.info('Найдено {} блюд', len(dishes))
        return dishes


dish_crud = DishCRUD()
