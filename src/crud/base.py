import uuid
from typing import Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import interfaces

from src.core.base_model import Base

ModelType = TypeVar('ModelType', bound=Base)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Базовый клаcc CRUD. При наследовании требуется указать типизацию.

    Модель, схему создания, схему обновления.
    Пример:
    CafeCRUD(CRUDBase[Cafe, CreateCafeScheme, UpdateCafeScheme])
    """

    def __init__(self, model: Type[ModelType], rel_map: Optional[dict[str, str]] = None) -> None:
        """Конструктор класса.

        Нужно указать модель, и реляционную зависимость в виде словаря, где ключ это название связи в схеме,
        а значение название связи в моделе. В случае, если значения не отличются, то дублируем в ключ и
        в значение.
        Пример:
        cafe_crud = CafeCRUD(model=Cafe, rel_map={'поле_в_схеме': 'поле_в_модели'})
        """
        self.model = model
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
        query = select(self.model).where(self.model.id == obj_id)
        if options:
            query = query.options(*options)
        result = await session.execute(query)

        return result.scalar_one_or_none()

    async def get_all(
        self,
        session: AsyncSession,
        options: Optional[List[interfaces.UserDefinedOption]] = None,
    ) -> List[ModelType]:
        """Для получения списка обектов, где есть связи, требуетсяя указать параметр options.

        Пример:
        from sqlalchemy.orm import selectinload

        await cafe_crud.get_all(
        session=session,
        options=[selectinload(Cafe.managers)])
        """
        query = select(self.model)
        if options:
            query = query.options(*options)
        result = await session.execute(query)
        return result.scalars().all()

    async def create(self, obj_in: CreateSchemaType, session: AsyncSession) -> ModelType:
        """Создание объекта с гибким поиском связей по карте rel_map."""
        input_data = obj_in.model_dump()
        db_obj = self.model()

        for pydantic_field, sqlalchemy_field in self.rel_map.items():
            if pydantic_field in input_data and input_data[pydantic_field]:
                related_model = getattr(self.model, sqlalchemy_field).property.mapper.class_

                query = select(related_model).where(related_model.id.in_(input_data[pydantic_field]))
                result = await session.execute(query)

                setattr(db_obj, sqlalchemy_field, list(result.scalars().all()))

        for field, value in input_data.items():
            if field not in self.rel_map and hasattr(db_obj, field):
                setattr(db_obj, field, value)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update(self, db_obj: ModelType, obj_in: UpdateSchemaType, session: AsyncSession) -> ModelType:
        """Обновление объекта с поддержкой PATCH-запросов и карты rel_map."""
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

            elif hasattr(db_obj, field):
                setattr(db_obj, field, value)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj
