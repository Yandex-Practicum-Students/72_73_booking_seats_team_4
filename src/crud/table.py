import uuid

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.table import Table
from schemas.table import TableCreate, TableInfo, TableUpdate


class TableCRUD(CRUDBase[Table, TableCreate, TableUpdate]):
    """CRUD-операции для столов в кафе."""

    def __init__(self) -> None:
        """Настраивает модель стола."""
        super().__init__(Table, TableInfo)

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
        tables = result.scalars().all()
        logger.info('Найдено {} столов для кафе {}', len(tables), cafe_id)
        return tables

    async def get_by_cafe_and_id(
        self,
        cafe_id: uuid.UUID,
        table_id: uuid.UUID,
        session: AsyncSession,
    ) -> Table | None:
        """Возвращает стол по ID, принадлежащий указанному кафе."""
        logger.info('Получение стола по cafe_id={} и table_id={}', cafe_id, table_id)
        query = (
            select(Table)
            .where(
                Table.id == table_id,
                Table.cafe_id == cafe_id,
            )
            .options(selectinload(Table.cafe))
        )
        result = await session.execute(query)
        table = result.scalar_one_or_none()

        if table is None:
            logger.warning('Стол не найден в кафе: cafe_id={}, table_id={}', cafe_id, table_id)
        else:
            logger.info('Стол найден в кафе: cafe_id={}, table_id={}', cafe_id, table_id)
        return table

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

    async def update(
        self,
        table: Table,
        table_update: TableUpdate,
        session: AsyncSession,
        redis: Redis,
    ) -> Table:
        """Обновляет стол с обработкой явного None."""
        update_data = table_update.model_dump(exclude_unset=True)

        if table_update.description is None and 'description' not in update_data:
            update_data['description'] = None
        return await super().update(table, update_data, session, redis)


table_crud = TableCRUD()
