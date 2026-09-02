from typing import Annotated

from fastapi import Query

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
