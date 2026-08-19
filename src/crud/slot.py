import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.slots import Slot
from schemas.slots import TimeSlotCreate, TimeSlotUpdate


class SlotCRUD(CRUDBase[Slot, TimeSlotCreate, TimeSlotUpdate]):
    """CRUD-операции для временных слотов."""

    def __init__(self) -> None:
        """Настраивает модель слота."""
        super().__init__(Slot)

    async def get_by_cafe(
        self,
        cafe_id: uuid.UUID,
        session: AsyncSession,
        *,
        show_active: bool | None = None,
    ) -> list[Slot]:
        """Возвращает слоты кафе, при необходимости фильтруя по активности."""
        statement = select(Slot).where(Slot.cafe_id == cafe_id).order_by(Slot.start_time)
        if show_active is not None:
            statement = statement.where(Slot.is_active.is_(show_active))
        result = await session.execute(statement)
        return list(result.scalars().all())


slot_crud = SlotCRUD()
