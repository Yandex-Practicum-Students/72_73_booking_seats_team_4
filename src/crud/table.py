import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.table import Table
from schemas.table import TableCreate, TableUpdate


class TableCRUD(CRUDBase[Table, TableCreate, TableUpdate]):
    """CRUD-операции для столов в кафе."""

    def __init__(self) -> None:
        """Настраивает модель стола."""
        super().__init__(Table)

    async def get(
        self,
        obj_id: uuid.UUID,
        session: AsyncSession,
    ) -> Table | None:
        """Возвращает стол вместе со связанным кафе."""
        logger.info('Получение стола по ID: {}', obj_id)
        return await super().get(
            obj_id,
            session,
            options=[selectinload(Table.cafe)],
        )

    async def get_all(
        self,
        session: AsyncSession,
    ) -> list[Table]:
        """Возвращает все столы вместе со связанным кафе."""
        logger.info('Получение всех столов')
        return await super().get_all(
            session,
            options=[selectinload(Table.cafe)],
        )

    async def get_by_cafe(
            self,
            cafe_id: uuid.UUID,
            session: AsyncSession,
            *,
            show_active: bool | None = None,
    ) -> list[Table]:
        """Возвращает столы кафе с фильтрацией по активности."""
        logger.info('Получение столов кафе: cafe_id={}, show_active={}', cafe_id, show_active)
        query = select(Table).where(Table.cafe_id == cafe_id)

        if show_active is not None:
            query = query.where(Table.is_active == show_active)

        query = query.options(selectinload(Table.cafe))
        result = await session.execute(query)
        tables = list(result.scalars().all())
        logger.info('Найдено {} столов для кафе {}', len(tables), cafe_id)
        return tables

    async def create_with_cafe(
            self,
            cafe_id: uuid.UUID,
            obj_in: TableCreate,
            session: AsyncSession,
    ) -> Table:
        """Создаёт стол с привязкой к кафе.

        Базовый метод create() не подходит, так как cafe_id приходит
        из URL (path parameter), а не из тела запроса TableCreate.
        """
        logger.info('Создание стола в кафе: cafe_id={}, seat_number={}', cafe_id, obj_in.seat_number)
        db_table = Table(
            cafe_id=cafe_id,
            seat_number=obj_in.seat_number,
            description=obj_in.description,
        )
        session.add(db_table)
        await session.commit()
        await session.refresh(db_table)
        logger.info('Стол создан: table_id={}, cafe_id={}', db_table.id, cafe_id)
        return await self.get(db_table.id, session)


table_crud = TableCRUD()
