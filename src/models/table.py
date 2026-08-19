import uuid

from sqlalchemy import UUID, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.booking import BookingTablesSlots
from models.cafe import Cafe

from core.base_model import Base, DescriptionMixin


class Table(Base, DescriptionMixin):
    """Модель стола в кафе."""

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('cafes.id', ondelete='NO ACTION'),
        nullable=False,
    )
    seat_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    cafe: Mapped['Cafe'] = relationship(
        'Cafe',
        back_populates='tables',
        lazy='selectin',
    )
    booking_tables_slots: Mapped[list['BookingTablesSlots']] = relationship(
        'BookingTablesSlots',
        back_populates='table',
        lazy='selectin',
    )

    def __repr__(self) -> str:
        return f'Стол {self.id} (кафе={self.cafe_id}, мест={self.seat_number})'
