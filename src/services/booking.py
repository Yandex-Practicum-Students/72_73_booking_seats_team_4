import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Booking, User


async def get_managers_by_booking(booking_id: uuid.UUID, session: AsyncSession) -> list[uuid.UUID]:
    """Получить ID всех менеджеров кафе, в котором сделано бронирование."""
    result = await session.execute(
        select(User.id)
        .join(Booking, User.cafe_id == Booking.cafe_id)
        .where(
            Booking.id == booking_id,
            User.role == 'MANAGER',
        ),
    )
    return list(result.scalars().all())
