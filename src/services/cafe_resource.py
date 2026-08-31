import uuid
from typing import Protocol, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from services.errors import EntityNotFoundError

from core.base_model import Base

Resource = TypeVar('Resource', bound=Base)


class CafeResourceReader(Protocol[Resource]):
    """Контракт чтения ресурса по его ID и ID кафе."""

    async def get_by_cafe_and_id(
        self,
        cafe_id: uuid.UUID,
        resource_id: uuid.UUID,
        session: AsyncSession,
    ) -> Resource | None:
        """Возвращает ресурс, принадлежащий кафе."""
        ...


async def get_cafe_resource_or_raise(
    cafe_id: uuid.UUID,
    resource_id: uuid.UUID,
    session: AsyncSession,
    reader: CafeResourceReader[Resource],
    not_found_message: str,
) -> Resource:
    """Возвращает ресурс кафе или сообщает, что связи нет."""
    resource = await reader.get_by_cafe_and_id(cafe_id, resource_id, session)
    if resource is None:
        raise EntityNotFoundError(not_found_message)
    return resource
