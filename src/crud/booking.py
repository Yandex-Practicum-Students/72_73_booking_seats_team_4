import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models import (
    Booking,
    BookingTablesSlots,
    Slot,
    User,
)
from schemas.booking import BookingCreate, BookingUpdate

from core.core_dependencies import redis_dep


class BookingCRUD(CRUDBase[Booking, BookingCreate, BookingUpdate]):
    """CRUD для бронирований."""

    def __init__(self) -> None:
        """Настройка экземпляра класса CRUD-операций Booking."""
        super().__init__(
            model=Booking,
            response_schema=BookingCreate,
            rel_map={'tables_slots': 'table_slot'},
        )

    async def create(
        self,
        obj_in: BookingCreate,
        session: AsyncSession,
        redis: redis_dep,
    ) -> Booking:
        """Создание бронирования с привязкой столов и слотов."""
        ...
        return Booking()

    async def get_managers_by_booking(
        self,
        booking_id: uuid.UUID,
        session: AsyncSession,
    ) -> list[uuid.UUID]:
        """Получить ID всех менеджеров кафе, привязанного к слотам бронирования."""
        query = (
            select(User.id)
            .join(Slot, Slot.cafe_id == User.cafe_id)
            .join(BookingTablesSlots, BookingTablesSlots.slot_id == Slot.id)
            .where(
                BookingTablesSlots.booking_id == booking_id,
                User.role == 'MANAGER',
            )
            .distinct()
        )
        result = await session.execute(query)
        return list(result.scalars().all())


booking_crud = BookingCRUD()
