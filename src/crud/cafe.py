import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.cafe import Cafe
from schemas.cafe import CafeCreate, CafeInfo, CafeUpdate


class CafeCRUD(CRUDBase[Cafe, CafeCreate, CafeUpdate]):
    """CRUD-операции для кафе и связанных менеджеров."""

    def __init__(self) -> None:
        """Настраивает модель кафе и соответствие поля менеджеров."""
        super().__init__(Cafe, CafeInfo, rel_map={'managers_id': 'managers'})

    async def get(self, obj_id: uuid.UUID, session: AsyncSession) -> Cafe | None:
        """Возвращает кафе вместе со списком менеджеров."""
        return await super().get(
            obj_id,
            session,
            options=[selectinload(Cafe.managers)],
        )

    async def get_all(
        self,
        session: AsyncSession,
        is_active: bool | None = None,
    ) -> list[Cafe]:
        """Возвращает все кафе вместе со списками менеджеров."""
        return await super().get_all(
            session,
            is_active=is_active,
            options=[selectinload(Cafe.managers)],
        )


cafe_crud = CafeCRUD()
