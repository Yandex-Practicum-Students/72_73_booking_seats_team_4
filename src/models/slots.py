import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.base_model import Base

if TYPE_CHECKING:
    from src.models.booking import Booking
    from src.models.cafe import Cafe


class Slot(Base):
    """Модель временного слота в кафе."""

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("cafes.id", ondelete="NO ACTION"),
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(
        Time(timezone=True),
        nullable=False,
    )
    end_time: Mapped[time] = mapped_column(Time(timezone=True), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    cafe: Mapped["Cafe"] = relationship(
        "Cafe",
        back_populates="slots",
        lazy="selectin",
    )
    bookings: Mapped[list["Booking"]] = relationship(
        "Booking",
        back_populates="slot",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"Слот {self.id} (кафе={self.cafe_id}, {self.start_time}-{self.end_time})"
