import json
import uuid
from typing import Generic, List, Optional, Type, TypeVar

from loguru import logger
from pydantic import BaseModel, RootModel
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import interfaces

from core.base_model import Base
from core.core_dependencies import redis_dep
from core.settings import settings

ModelType = TypeVar('ModelType', bound=Base)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)
ResponseSchemaType = TypeVar('ResponseSchemaType', bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Базовый клаcc CRUD. При наследовании требуется указать типизацию.

    Модель, схему создания, схему обновления.
    Пример:
    CafeCRUD(CRUDBase[Cafe, CreateCafeScheme, UpdateCafeScheme])
    """

    def __init__(
        self,
        model: Type[ModelType],
        response_schema: Type[ResponseSchemaType],
        rel_map: Optional[dict[str, str]] = None,
    ) -> None:
        """Конструктор класса.

        Нужно указать модель, и реляционную зависимость в виде словаря, где ключ это название связи в схеме,
        а значение название связи в моделе. В случае, если значения не отличются, то дублируем в ключ и
        в значение.
        Пример:
        cafe_crud = CafeCRUD(model=Cafe, response_schema=CafeInfo, rel_map={'поле_в_схеме': 'поле_в_модели'})
        """
        self.model = model
        self.response_schema = response_schema
        if rel_map:
            self.rel_map = rel_map
        else:
            self.rel_map = {}

    async def get(
        self,
        obj_id: uuid.UUID,
        session: AsyncSession,
        options: Optional[List[interfaces.UserDefinedOption]] = None,
    ) -> Optional[ModelType]:
        """Для получения обекта где есть связи, требуетсяя указать параметр options.

        Пример:
        from sqlalchemy.orm import selectinload

        await cafe_crud.get(
        session=session,
        obj_id=cafe_id,
        options=[selectinload(Cafe.managers)])
        """
        db_obj_key = f'{self.model.__tablename__}:{obj_id}'
        try:
            query = select(self.model).where(self.model.id == obj_id)
            if options:
                query = query.options(*options)
            result = await session.execute(query)
            result = result.scalar_one_or_none()
            if result is None:
                logger.info(f'Объект "{db_obj_key}" не найден в бд postgres')
                return result

            logger.info(f'Объект "{db_obj_key}" получен из бд Postgres.')

            return result
        except Exception as e:
            logger.error(f'Ошибка при получении объекта "{db_obj_key}":\n {e}')
            raise

    async def get_with_cache(
        self,
        obj_id: uuid.UUID,
        session: AsyncSession,
        redis: redis_dep,
        ex_redis: int = settings.redis_cache_expire_seconds,
        options: Optional[List[interfaces.UserDefinedOption]] = None,
    ) -> Optional[ResponseSchemaType]:
        """Для получения закэшированного обекта из Redis. Где есть связи, требуетсяя указать параметр options.

        Пример:
        from sqlalchemy.orm import selectinload

        await cafe_crud.get(
        session: AsyncSession = session,
        obj_id=cafe_id,
        redis: Redis = redis_dep,
        ex_redis: int = 10, хранение в секундах если не устраивает стандартный 3600
        options=[selectinload(Cafe.managers)])
        """
        db_obj_key = f'{self.model.__tablename__}:{obj_id}'
        try:
            try:
                cached_result = await redis.get(db_obj_key)
            except RedisError as e:
                logger.error(f'Ошибка redis для ключа "{db_obj_key}":\n {e}')
                cached_result = None

            if cached_result:
                logger.info(f'Объект "{db_obj_key}" получен из Redis')
                return self.response_schema.model_validate_json(cached_result)

            if not options:
                db_obj = await self.get(obj_id=obj_id, session=session)
            else:
                db_obj = await self.get(obj_id=obj_id, session=session, options=options)

            if db_obj is None:
                return None

            pydantic_obj = self.response_schema.model_validate(db_obj)
            json_str = pydantic_obj.model_dump_json()
            try:
                await redis.set(db_obj_key, json_str, ex=ex_redis)
                logger.info(f'Объект "{db_obj_key}" записан в Redis')
            except RedisError as e:
                logger.error(f'Ошибка redis для ключа "{db_obj_key}":\n {e}')

            return pydantic_obj

        except Exception as e:
            logger.error(f'Ошибка при получении объекта "{db_obj_key}":\n {e}')
            raise

    async def get_all(
        self,
        session: AsyncSession,
        is_active: Optional[bool] = None,
        options: Optional[List[interfaces.UserDefinedOption]] = None,
    ) -> List[ModelType]:
        """Для получения списка обектов, где есть связи, требуетсяя указать параметр options.

        Пример:
        from sqlalchemy.orm import selectinload

        await cafe_crud.get_all(
        session=session,
        is_active=True,
        options=[selectinload(Cafe.managers)])
        """
        all_key = f'{self.model.__tablename__}'
        try:
            query = select(self.model)
            if is_active is not None:
                query = query.where(self.model.is_active == is_active)
            if options:
                query = query.options(*options)
            result = await session.execute(query)
            if not result:
                logger.info(f'Объекты "{all_key}" не найден в бд postgres')
            return result.scalars().all()
        except Exception as e:
            logger.error(f'Ошибка при получении объектов "{all_key}":\n {e}')
            raise

    async def get_all_with_cache(
        self,
        session: AsyncSession,
        redis: redis_dep,
        is_active: Optional[bool] = None,
        ex_redis: int = settings.redis_cache_expire_seconds,
        options: Optional[List[interfaces.UserDefinedOption]] = None,
    ) -> List[ResponseSchemaType]:
        """Для получения списка обектов, где есть связи, требуетсяя указать параметр options.

        Пример:
        from sqlalchemy.orm import selectinload

        await cafe_crud.get_all(
        session=session,
        redis: redis_dep,
        is_active=None,   указать bool
        ex_redis=3600,    время жизни кэша в редис если не нравится стандартное
        options=[selectinload(Cafe.managers)])
        """
        redis_all_key = self._all_cache_key(is_active)

        try:
            try:
                cached_result = await redis.get(redis_all_key)
            except RedisError as e:
                logger.error(f'Ошибка redis для ключа "{redis_all_key}":\n {e}')
                cached_result = None

            list_schema = RootModel[List[self.response_schema]]
            if cached_result:
                logger.info(f'Список "{redis_all_key}" получен из Redis')
                return list_schema.model_validate_json(cached_result).root

            db_obj = await CRUDBase.get_all(
                self,
                session=session,
                is_active=is_active,
                options=options,
            )

            if not db_obj:
                return []

            validated_models = list_schema.model_validate(db_obj)
            raw_dicts = validated_models.model_dump(mode='json')
            data_for_redis = json.dumps(raw_dicts, default=str)

            try:
                await redis.set(redis_all_key, data_for_redis, ex=ex_redis)
                logger.info(f'Список "{redis_all_key}" записан в Redis')
            except RedisError as e:
                logger.error(f'Ошибка redis для ключа "{redis_all_key}":\n {e}')

            return validated_models.root

        except Exception as e:
            logger.error(f'Ошибка при получении объекта "{redis_all_key}":\n {e}')
            raise

    async def create(
        self,
        obj_in: CreateSchemaType,
        session: AsyncSession,
        redis: redis_dep,
    ) -> ResponseSchemaType:
        """Создание объекта с гибким поиском связей по карте rel_map."""
        redis_all_keys = self._all_cache_keys()
        try:
            input_data = obj_in.model_dump()
            db_obj = self.model()

            for pydantic_field, sqlalchemy_field in self.rel_map.items():
                if pydantic_field in input_data and input_data[pydantic_field]:
                    related_model = getattr(self.model, sqlalchemy_field).property.mapper.class_

                    query = select(related_model).where(related_model.id.in_(input_data[pydantic_field]))
                    result = await session.execute(query)

                    setattr(db_obj, sqlalchemy_field, list(result.scalars().all()))

            for field, value in input_data.items():
                if field in self.rel_map or field in self.rel_map.values():
                    continue

                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            session.add(db_obj)
            await session.commit()
            logger.info(f'Объект {self.model.__tablename__} с ID {db_obj.id} успешно сохранен')
            await self._del_redis_key(*redis_all_keys, redis=redis)

            return self.response_schema.model_validate(db_obj)
        except ConnectionError as e:
            logger.error(f'Ошибка подключения к бд при сохранении объекта: {db_obj}.\n {e}')
            raise
        except Exception as e:
            logger.error(f'Ошибка при сохранении объекта: {db_obj}.\n {e}')
            raise

    async def update(
        self,
        db_obj: ModelType,
        obj_in: UpdateSchemaType,
        session: AsyncSession,
        redis: redis_dep,
    ) -> ResponseSchemaType:
        """Обновление объекта с поддержкой карты rel_map."""
        redis_all_keys = self._all_cache_keys()
        redis_obj_key = f'{self.model.__tablename__}:{db_obj.id}'
        try:
            update_data = obj_in.model_dump(exclude_unset=True)

            for field, value in update_data.items():
                if field in self.rel_map:
                    sqlalchemy_field = self.rel_map[field]
                    related_model = getattr(self.model, sqlalchemy_field).property.mapper.class_

                    if value:
                        query = select(related_model).where(related_model.id.in_(value))
                        result = await session.execute(query)
                        setattr(db_obj, sqlalchemy_field, list(result.scalars().all()))
                    else:
                        setattr(db_obj, sqlalchemy_field, [])

                elif field not in self.rel_map.values() and hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            session.add(db_obj)
            await session.commit()
            logger.info(
                f'Объект "{redis_obj_key}" успешно зафискирован в бд при'
                f'обновлении. изменененные атрибуты объекта:\n {update_data}',
            )
            await self._del_redis_key(*redis_all_keys, redis_obj_key, redis=redis)

            return self.response_schema.model_validate(db_obj)

        except ConnectionError as e:
            logger.error(f'Ошибка подключения к бд при сохранении объекта: {db_obj}.\n {e}')
            raise
        except Exception as e:
            logger.error(f'Ошибка при обнвлении объекта "{db_obj}":\n {e}')
            raise

    def _all_cache_key(self, is_active: Optional[bool] = None) -> str:
        """Возвращает отдельный ключ для каждого фильтра активности."""
        suffix = 'all' if is_active is None else f'all:{str(is_active).lower()}'
        return f'{self.model.__tablename__}:{suffix}'

    def _all_cache_keys(self) -> tuple[str, str, str]:
        """Возвращает все ключи списков, которые меняются при записи."""
        return (
            self._all_cache_key(),
            self._all_cache_key(True),
            self._all_cache_key(False),
        )

    @staticmethod
    async def _del_redis_key(*args: str, redis: redis_dep) -> None:
        redis_keys = ', '.join(args)
        try:
            await redis.delete(*args)
            logger.info(f'Кэш очищен для ключей: "{redis_keys}"')
        except RedisError as e:
            logger.error(f'Ошибка при удалении ключей redis "{redis_keys}":\n {e}')
        except Exception as e:
            logger.error(f'Ошибка при удалении ключей redis "{redis_keys}":\n {e}')
            raise
