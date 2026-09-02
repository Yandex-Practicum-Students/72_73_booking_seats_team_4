import uuid
from dataclasses import dataclass
from typing import Annotated, Optional

from fastapi import Query

from exceptions.common import PermissionDeniedError
from models.user import User, UserRole

Boolean = Annotated[bool | None, Query()]


def resolve_show_active(
    user: User,
    requested: bool | None,
    *,
    manager_can_filter: bool = False,
) -> bool | None:
    """Возвращает допустимый фильтр активности с учётом роли."""
    if user.role == UserRole.ADMIN:
        return requested
    if user.role == UserRole.MANAGER and manager_can_filter:
        return True if requested is None else requested
    return True


def filter_user_role_manager_for_cafe_id(
    user: User,
    cafe_id: Optional[uuid.UUID] = None,
) -> Optional[uuid.UUID]:
    """Возвращает cafe_id для фильтра, менеджеру — только его кафе."""
    if user.role == UserRole.MANAGER:
        if user.cafe_id is None:
            raise PermissionDeniedError('Менеджер не привязан ни к одному кафе')
        cafe_id = user.cafe_id
    return cafe_id


@dataclass
class QueryParamFilter:
    """Фильтр query-параметров."""

    cafe_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
