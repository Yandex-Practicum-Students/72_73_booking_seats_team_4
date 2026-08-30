import uuid
from typing import Optional

from loguru import logger
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
        logger.info('Получение кафе по ID: {}', obj_id)
        cafe = await super().get(obj_id, session, options=[selectinload(Cafe.managers)])
        if cafe:
            logger.success('Кафе найдено: cafe_id={}, name={}', obj_id, cafe.name)
        else:
            logger.warning('Кафе не найдено: cafe_id={}', obj_id)
        return cafe

    async def get_all(
        self,
        session: AsyncSession,
        show_active: Optional[bool] = None,
    ) -> list[Cafe]:
        """Возвращает все кафе вместе со списками менеджеров с фильтрацией по активности."""
        logger.info('Получение всех кафе: show_active={}', show_active)

        cafes = await super().get_all(
            session=session,
            is_active=show_active,
            options=[selectinload(Cafe.managers)],
        )

        logger.success('Найдено {} кафе', len(cafes))
        return cafes


cafe_crud = CafeCRUD()
