import uuid
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import interfaces, selectinload

from crud.base import CRUDBase
from models.booking import Booking, BookingTablesSlots
from models.user import User, UserRole
from schemas.booking import BookingCreate, BookingInfo, BookingUpdate


def create_obj_booking_tables_slots(
    data: dict,
    booking_id: Optional[uuid.UUID] = None,
) -> list[BookingTablesSlots]:
    """Создает новый объект модели BookingTablesSlots из поступивших данных."""
    logger.info('Создание нового объекта модели BookingTablesSlots.')
    table_slot = []
    booking_table_slot = data.pop('tables_slots')
    for item in booking_table_slot:
        if booking_id is not None:
            new_table_slot = BookingTablesSlots(
                booking_id=booking_id,
                table_id=item['table_id'],
                slot_id=item['slot_id'],
            )
        else:
            new_table_slot = BookingTablesSlots(table_id=item['table_id'], slot_id=item['slot_id'])
        table_slot.append(new_table_slot)
    logger.info('Создано {} объектов BookingTablesSlots.', len(table_slot))
    return table_slot


class BookingCRUD(CRUDBase[Booking, BookingCreate, BookingUpdate]):
    """CRUD-операции бронирования заказа."""

    def __init__(self) -> None:
        """Инициализирует CRUD для модели бронирования."""
        super().__init__(Booking, BookingInfo)

    async def get_all(
        self,
        session: AsyncSession,
        options: Optional[list[interfaces.UserDefinedOption]] = None,
        show_active: Optional[bool] = None,
        cafe_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> list[Booking]:
        """Возвращает список объектов бронирования.

        Переопределяет базовый метод для возможносмти
        фильтрации списка бронирований по параметрам: user_id, cafe_id, show_active
        """
        logger.info('Получение списка бронирований')
        all_bookings = select(self.model)
        if user_id is not None:
            all_bookings = all_bookings.where(self.model.user_id == user_id)
        if cafe_id is not None:
            all_bookings = all_bookings.where(self.model.cafe_id == cafe_id)
        if show_active is not None:
            all_bookings = all_bookings.where(self.model.is_active == show_active)
        if options is None:
            options = [
                selectinload(self.model.user),
                selectinload(self.model.cafe),
                selectinload(self.model.tables_slots.and_(BookingTablesSlots.is_active)),
            ]
        all_bookings = all_bookings.options(*options)
        result = await session.execute(all_bookings)
        bookings = result.scalars().all()
        logger.info('Найдено {} бронирований', len(bookings))
        return bookings

    async def get_managers_by_booking(
        self,
        booking_id: uuid.UUID,
        session: AsyncSession,
    ) -> list[uuid.UUID]:
        """Получить ID всех менеджеров кафе, в котором сделано бронирование."""
        result = await session.execute(
            select(User.id)
            .join(Booking, User.cafe_id == Booking.cafe_id)
            .where(
                Booking.id == booking_id,
                User.role == UserRole.MANAGER,
            ),
        )
        return list(result.scalars().all())

    async def create(
        self,
        obj_in: BookingCreate,
        session: AsyncSession,
        current_user: User,
    ) -> Booking:
        """Создание объекта бронирования.

        Переопределяет базовый метод create, создавая
        из одного запроса объект модели Booking и объект модели BookingTableSlot.
        """
        logger.info('Создание нового бронирования')
        obj_in_data = obj_in.model_dump()
        obj_in_data['user_id'] = current_user.id
        obj_in_data['tables_slots'] = create_obj_booking_tables_slots(obj_in_data)
        new_booking_db = self.model(**obj_in_data)
        session.add(new_booking_db)
        await session.flush()
        new_booking_db = await self.get(
            obj_id=new_booking_db.id,
            session=session,
            options=[
                selectinload(Booking.user),
                selectinload(Booking.cafe),
                selectinload(Booking.tables_slots.and_(BookingTablesSlots.is_active)),
            ],
        )
        logger.info('Бронирование {} создано.', new_booking_db.id)
        return new_booking_db

    async def update(
        self,
        db_booking: Booking,
        obj_in: BookingUpdate,
        session: AsyncSession,
    ) -> Booking:
        """Обновляет объект бронирования."""
        logger.info('Обновление бронирования id {}.', db_booking.id)
        update_data = obj_in.model_dump(exclude_unset=True)

        if 'tables_slots' in update_data:
            for item in db_booking.tables_slots:
                item.is_active = False
        if 'tables_slots' in update_data and not (
            'is_active' in update_data and not update_data['is_active']
        ):
            update_data['tables_slots'] = create_obj_booking_tables_slots(
                update_data,
                booking_id=db_booking.id,
            )
            db_booking.tables_slots.extend(update_data['tables_slots'])
            del update_data['tables_slots']

        for field, value in update_data.items():
            if hasattr(db_booking, field):
                setattr(db_booking, field, value)

        session.add(db_booking)
        await session.flush()
        update_db_booking = await self.get(
            obj_id=db_booking.id,
            session=session,
            options=[
                selectinload(Booking.user),
                selectinload(Booking.cafe),
                selectinload(Booking.tables_slots.and_(BookingTablesSlots.is_active)),
            ],
        )
        logger.info('Обновление бронирования id {} завершено.', db_booking.id)
        return update_db_booking


booking_crud = BookingCRUD()
