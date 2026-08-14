import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_model import Base

if TYPE_CHECKING:
    from src.models.booking_tables_slots import BookingTablesSlots
    from src.models.cafe import Cafe


class Slot(Base):
    """Модель временного слота в кафе."""

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("cafes.id", ondelete="NO ACTION"),
    )
    start_time: Mapped[time] = mapped_column(
        Time(timezone=True),
    )
    end_time: Mapped[time] = mapped_column(
        Time(timezone=True),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
    )

    cafe: Mapped["Cafe"] = relationship(
        "Cafe",
        back_populates="slots",
        lazy="selectin",
    )
    booking_tables_slots: Mapped[list["BookingTablesSlots"]] = relationship(
        "BookingTablesSlots",
        back_populates="slot",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f'Слот {self.id} (кафе={self.cafe_id}, {self.start_time}-{self.end_time})'
