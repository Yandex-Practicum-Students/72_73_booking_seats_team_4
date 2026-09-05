import uuid
from datetime import date

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from exceptions.common import BadRequestError
from models.booking import Booking, BookingTablesSlots, StatusBooking
from models.slots import Slot
from schemas.slots import TimeSlotCreate, TimeSlotInfo, TimeSlotUpdate


class SlotCRUD(CRUDBase[Slot, TimeSlotCreate, TimeSlotUpdate]):
    """CRUD-операции для временных слотов."""

    def __init__(self) -> None:
        """Настраивает модель слота."""
        super().__init__(Slot, TimeSlotInfo)

    async def get(
        self,
        obj_id: uuid.UUID,
        session: AsyncSession,
    ) -> Slot | None:
        """Возвращает слот вместе со связанным кафе."""
        logger.info('Получение слота по ID: {}', obj_id)
        return await super().get(
            obj_id,
            session,
            options=[selectinload(Slot.cafe)],
        )

    async def get_all(
        self,
        session: AsyncSession,
    ) -> list[Slot]:
        """Возвращает все слоты вместе со связанным кафе."""
        logger.info('Получение всех слотов')
        return await super().get_all(
            session,
            options=[selectinload(Slot.cafe)],
        )

    async def get_by_cafe(
        self,
        cafe_id: uuid.UUID,
        session: AsyncSession,
        *,
        show_active: bool | None = None,
        table_id: uuid.UUID | None = None,
        booking_date: date | None = None,
    ) -> list[Slot]:
        """Возвращает слоты кафе с фильтрацией по активности и занятости."""
        logger.info(
            'Получение слотов кафе: cafe_id={}, show_active={}, table_id={}, booking_date={}',
            cafe_id,
            show_active,
            table_id,
            booking_date,
        )
        query = select(Slot).where(Slot.cafe_id == cafe_id)

        if show_active is not None:
            query = query.where(Slot.is_active == show_active)

        # Если выбран стол и дата - исключаем слоты, занятые этим столом
        if table_id is not None and booking_date is not None:
            booked_slots = (
                select(BookingTablesSlots.slot_id)
                .join(Booking, Booking.id == BookingTablesSlots.booking_id)
                .where(
                    BookingTablesSlots.table_id == table_id,
                    Booking.booking_date == booking_date,
                    Booking.status != StatusBooking.CANCELED,
                    Booking.is_active.is_(True),
                )
            )
            query = query.where(~Slot.id.in_(booked_slots))

        query = query.options(selectinload(Slot.cafe))
        result = await session.execute(query)
        slots = result.scalars().all()
        logger.info('Найдено {} слотов для кафе {}', len(slots), cafe_id)
        return slots

    async def get_by_cafe_and_id(
        self,
        cafe_id: uuid.UUID,
        slot_id: uuid.UUID,
        session: AsyncSession,
    ) -> Slot | None:
        """Возвращает слот по ID, принадлежащий указанному кафе."""
        logger.info('Получение слота по cafe_id={} и slot_id={}', cafe_id, slot_id)
        query = (
            select(Slot)
            .where(
                Slot.id == slot_id,
                Slot.cafe_id == cafe_id,
            )
            .options(selectinload(Slot.cafe))
        )
        result = await session.execute(query)
        slot = result.scalar_one_or_none()

        if slot is None:
            logger.warning('Слот не найден в кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
        else:
            logger.info('Слот найден в кафе: cafe_id={}, slot_id={}', cafe_id, slot_id)
        return slot

    async def create_with_cafe(
        self,
        cafe_id: uuid.UUID,
        obj_in: TimeSlotCreate,
        session: AsyncSession,
    ) -> Slot:
        """Создаёт слот с привязкой к кафе.

        Базовый метод create() не подходит, так как cafe_id приходит
        из URL (path parameter), а не из тела запроса TimeSlotCreate.
        """
        logger.info(
            'Создание слота в кафе: cafe_id={}, start_time={}, end_time={}',
            cafe_id,
            obj_in.start_time,
            obj_in.end_time,
        )
        db_slot = Slot(
            cafe_id=cafe_id,
            start_time=obj_in.start_time,
            end_time=obj_in.end_time,
            description=obj_in.description,
        )
        session.add(db_slot)
        try:
            await session.commit()
        except IntegrityError as error:
            logger.error(f'Нарушение целостности БД при изменении {self.model.__tablename__}: {error}')
            message = f'{self.model.__tablename__} с такими параметрами уже существует'
            raise BadRequestError(message) from error
        await session.refresh(db_slot)
        logger.info('Слот создан: slot_id={}, cafe_id={}', db_slot.id, cafe_id)
        return await self.get(db_slot.id, session)


slot_crud = SlotCRUD()
