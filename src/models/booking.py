import uuid
from datetime import date
from enum import StrEnum
from typing import List, Optional

from sqlalchemy import UUID, CheckConstraint, Date, Enum, ForeignKey, Index, Integer, String
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
    booking: Mapped['Booking'] = relationship('Booking', back_populates='tables_slots', lazy='selectin')
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

    __table_args__ = (
        Index(
            'uniq_active_booking_table_slot',
            'table_id',
            'slot_id',
            unique=True,
            postgresql_where='is_active = true',
        ),
    )


class Booking(Base):
    """Модель бронирования заказов."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('users.id', name='fk_booking_user_id_user'),
        index=True,
    )
    user: Mapped['User'] = relationship('User')  # noqa: F821
    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('cafes.id', name='fk_booking_cafe_id_cafes'),
        index=True,
    )
    cafe: Mapped['Cafe'] = relationship('Cafe')  # noqa: F821
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    guest_number: Mapped[int] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(String(BOOKING_NOTE_MAX_LENGTH), nullable=True)
    status: Mapped[StatusBooking] = mapped_column(
        Enum(StatusBooking, name='status_booking_enum'),
        default=StatusBooking.BOOKING,
        server_default=StatusBooking.BOOKING.value,
        index=True,
    )
    reminder_minutes_before: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=180,
        server_default='180',
    )
    tables_slots: Mapped[List['BookingTablesSlots']] = relationship(
        'BookingTablesSlots',
        back_populates='booking',
        lazy='selectin',
    )
    notifications: Mapped[List['BookingNotification']] = relationship(  # noqa: F821
        'BookingNotification',
        back_populates='booking',
        lazy='selectin',
    )

    __table_args__ = (
        CheckConstraint(
            'reminder_minutes_before IS NULL OR reminder_minutes_before > 0',
            name='check_booking_reminder_minutes_positive',
        ),
        Index('user_booking_date', 'user_id', 'booking_date'),
    )
