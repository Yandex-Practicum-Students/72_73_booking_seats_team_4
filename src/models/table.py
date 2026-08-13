import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_model import Base

from src.models.booking import BookingTablesSlots
from src.models.cafe import Cafe


class Table(Base):
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
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


    cafe: Mapped["Cafe"] = relationship(
        "Cafe",
        back_populates="tables",
        lazy="selectin",
    )
    bookings: Mapped[list["BookingTablesSlots"]] = relationship(
        "Booking",
        back_populates="table",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f'Стол {self.id} (кафе={self.cafe_id}, мест={self.seat_number})'
