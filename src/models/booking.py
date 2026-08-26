import uuid
from datetime import date
from enum import StrEnum
from typing import List, Optional

from sqlalchemy import UUID, Date, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_model import Base
from core.constants import BOOKING_NOTE_MAX_LENGTH


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

    __tablename__ = 'bookingtableslots'
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('bookings.id', name='fk_booking_id_booking_tables_slots'),
        index=True,
    )
    booking: Mapped['Booking'] = relationship('Booking', back_populates='table_slot', lazy='selectin')
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('tables.id', name='fk_tables_id_booking_tables_slots'),
        index=True,
    )
    table: Mapped['Table'] = relationship('Table', back_populates='booking_tables_slots', lazy='selectin')  # noqa: F821
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('slots.id', name='fk_slots_id_booking_tables_slots'),
        index=True,
    )
    slot: Mapped['Slot'] = relationship('Slot', back_populates='booking_tables_slots', lazy='selectin')  # noqa: F821


class Booking(Base):
    """Модель бронирования заказов."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('users.id', name='fk_booking_user_id_user'),
        index=True,
    )
    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('cafes.id', name='fk_booking_cafe_id_cafes'),
        index=True,
    )
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    guest_number: Mapped[int] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(String(BOOKING_NOTE_MAX_LENGTH), nullable=True)
    status: Mapped[StatusBooking] = mapped_column(
        Enum(StatusBooking, name='status_booking_enum'),
        default=StatusBooking.BOOKING,
        server_default=StatusBooking.BOOKING.value,
        index=True,
    )
    table_slot: Mapped[List['BookingTablesSlots']] = relationship(
        'BookingTablesSlots',
        back_populates='booking',
        lazy='selectin',
    )
    notifications: Mapped[List['BookingNotification']] = relationship(  # noqa: F821
        'BookingNotification',
        back_populates='booking',
        lazy='selectin',
    )

    __table_args__ = (Index('user_booking_date', 'user_id', 'booking_date'),)
