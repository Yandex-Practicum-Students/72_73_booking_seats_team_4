import uuid
from datetime import time

from sqlalchemy import UUID, ForeignKey, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_model import Base, DescriptionMixin


class Slot(Base, DescriptionMixin):
    """Модель временного слота в кафе."""

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey('cafes.id', name='fk_cafe_id_slot', ondelete='NO ACTION'),
        index=True,
    )
    start_time: Mapped[time] = mapped_column(
        Time(timezone=True),
    )
    end_time: Mapped[time] = mapped_column(
        Time(timezone=True),
    )
    cafe: Mapped['Cafe'] = relationship(  # noqa: F821
        'Cafe',
        back_populates='slots',
        lazy='selectin',
    )
    booking_tables_slots: Mapped[list['BookingTablesSlots']] = relationship(  # noqa: F821
        'BookingTablesSlots',
        back_populates='slot',
        lazy='selectin',
    )

    def __repr__(self) -> str:
        return f'Слот {self.id} (кафе={self.cafe_id}, {self.start_time}-{self.end_time})'
