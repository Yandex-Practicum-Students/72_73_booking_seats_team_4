import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, tuple_
from sqlalchemy.orm import select, selectinload

from api.errors import APIError
from crud.booking import booking_crud
from models.booking import Booking, BookingTablesSlots, StatusBooking
from models.slots import Slot
from models.table import Table
from models.user import User, UserRole

from core.db import DBSession


class BookingNotFoundError(APIError):
    """Бронирование не найдено."""

    def __init__(self) -> None:
        """Бронирование не найдено."""
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message='Бронирование не найдено.',
        )


class BookingAlreadyExistsError(APIError):
    """Бронирование уже существует."""

    def __init__(self) -> None:
        """Бронирование уже существует."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Бронирование уже существует.',
        )


class CrossSlotsExistsError(APIError):
    """Существует бронирование с пересекающимися слотами."""

    def __init__(self) -> None:
        """Существует бронирование с пересекающимися слотами."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='У пользователя есть бронирования с пересекающимися слотами.',
        )


def split_tables_slots(tables_slots: list[tuple[int, int]]) -> tuple[list, list, list]:
    """Обрабатывает поле tables_slots из запроса.

    Разбивает на следующие списки для дальнейшего использования:
    пары стол_id-слот_id, столы_id, слоты_id.
    """
    table_slot_ids = [(item.table_id, item.slot_id) for item in tables_slots]
    table_ids = [table_id for table_id, slot_id in table_slot_ids]
    slot_ids = [slot_id for table_id, slot_id in table_slot_ids]
    return table_slot_ids, table_ids, slot_ids


async def get_booking_or_raise(
    booking_id: uuid.UUID,
    session: DBSession,
) -> Booking:
    """Возвращает бронирование или сообщает, что объект не найден."""
    booking = await booking_crud.get(
        obj_id=booking_id,
        session=session,
        options=[
            selectinload(Booking.user),
            selectinload(Booking.cafe),
            selectinload(Booking.table_slot),
        ],
    )
    if booking is None:
        raise BookingNotFoundError
    return booking


async def check_user_permission(
    booking: Booking,
    user: User,
) -> None:
    """Проверяет наличие права доступа к бронированию у пользователя и менеджера."""
    if user.role == UserRole.USER and user.id != booking.user_id:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='Доступ запрещен.',
        )
    if user.role == UserRole.MANAGER and (user.id != booking.user_id and user.cafe_id != booking.cafe_id):
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='Доступ запрещен.',
        )


async def check_double_booking_exsist(
    session: DBSession,
    cafe_id: uuid.UUID,
    booking_date: date,
    table_slot_ids: list,
) -> None:
    """Проверяет на наличе повторного бронирования."""
    booking = await session.execute(
        select(Booking)
        .join(Booking.table_slot)
        .where(
            Booking.cafe_id == cafe_id,
            Booking.booking_date == booking_date,
            Booking.status != StatusBooking.CANCELED,
            tuple_(BookingTablesSlots.table_id, BookingTablesSlots.slot_id).in_(table_slot_ids),
        ),
    )
    if booking.scalars().first() is not None:
        raise BookingAlreadyExistsError


async def check_user_have_same_slot(
    session: DBSession,
    booking_date: date,
    user_id: uuid.UUID,
    slot_ids: list,
) -> None:
    """Проверяет наличие у пользователя бронирований с пересекающимися слотами."""
    slots = await session.execute(select(Slot).where(Slot.id.in_(slot_ids)))
    start_end_time_slots_new_booking = [(slot.start_time, slot.end_time) for slot in slots.scalars().all()]
    cross_slots = [
        and_(Slot.start_time < new_end, new_start < Slot.end_time)
        for new_start, new_end in start_end_time_slots_new_booking
    ]
    bookings_user_cros_slots = await session.execute(
        select(Booking)
        .join(Booking.table_slot)
        .join(BookingTablesSlots.slot)
        .where(
            Booking.user_id == user_id,
            Booking.booking_date == booking_date,
            Booking.status != StatusBooking.CANCELED,
            or_(*cross_slots),
        ),
    )
    if bookings_user_cros_slots.scalars().first() is not None:
        raise CrossSlotsExistsError


async def check_cafe_has_tables_slots(
    session: DBSession,
    cafe_id: uuid.UUID,
    table_ids: list,
    slot_ids: list,
) -> None:
    """Проверяет существует ли в кафе указанные столы и слоты."""
    found_table_ids = await session.execute(
        select(Table.id).where(
            Table.cafe_id == cafe_id,
            Table.id.in_(table_ids),
            Table.is_active,
        ),
    )
    found_table_ids = set(found_table_ids.scalars().all())
    unknown_table_ids = set(table_ids) - found_table_ids
    if unknown_table_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'В кафе не найдены столы(по id) {unknown_table_ids}',
        )

    found_slot_ids = await session.execute(
        select(Slot.id).where(
            Slot.cafe_id == cafe_id,
            Slot.id.in_(slot_ids),
            Slot.is_active,
        ),
    )
    found_slot_ids = set(found_slot_ids.scalars().all())
    unknown_slot_ids = set(slot_ids) - found_slot_ids
    if unknown_slot_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'В кафе не найдены слот с id {unknown_slot_ids}',
        )
