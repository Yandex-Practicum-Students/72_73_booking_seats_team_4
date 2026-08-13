import uuid
from datetime import date
from enum import StrEnum
from typing import Optional

from sqlalchemy import UUID, Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base_model import Base


class StatusBooking(StrEnum):
    """Класс описания статуса бронирования."""

    BOOKING = 'BOOKING'
    CANCELED = 'CANCELED'
    ACTIVE = 'ACTIVE'
    COMPLETED = 'COMPLETED'


class BookingTablesSlots(Base):
    """Промежуточная модель.

    Описывает отношение многие ко многим
    между моделями Booking, Tables, Slots.
    """

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('booking.id', name='fk_booking_id_booking_tables_slots'),
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('tables.id', name='fk_tables_id_booking_tables_slots'),
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('slots.id', name='fk_slots_id_booking_tables_slots'),
    )


class Booking(Base):
    """Модель бронирования заказов."""

    user_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', name='fk_booking_user_id_user'))
    cafe_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cafes.id', name='fk_booking_cafe_id_cafes'))
    booking_date: Mapped[date] = mapped_column(Date)
    guest_number: Mapped[int] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[StatusBooking] = mapped_column(
        Enum(StatusBooking, name='status_booking_enum'),
        default=StatusBooking.BOOKING,
        server_default=StatusBooking.BOOKING.value,
    )
