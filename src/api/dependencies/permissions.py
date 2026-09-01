from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, status

from api.dependencies.logging import get_current_user_with_logging, get_me_user_with_logging
from api.errors import APIError
from models.user import User, UserRole
from services.user import is_admin

CurrentUser = Annotated[User, Depends(get_current_user_with_logging)]
MeUser = Annotated[User, Depends(get_me_user_with_logging)]


async def get_staff_user(user: CurrentUser) -> User:
    """Разрешает доступ администраторам и менеджерам."""
    if user.role in (UserRole.ADMIN, UserRole.MANAGER):
        return user
    raise APIError(
        status_code=status.HTTP_403_FORBIDDEN,
        message='Доступ запрещён.',
    )


async def get_admin_user(user: CurrentUser) -> User:
    """Разрешает доступ только администраторам."""
    if is_admin(user):
        return user
    raise APIError(
        status_code=status.HTTP_403_FORBIDDEN,
        message='Доступ запрещён.',
    )


StaffUser = Annotated[User, Depends(get_staff_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]


class ActiveResource(Protocol):
    """Ресурс, доступность которого определяется флагом активности."""

    is_active: bool


def ensure_active_resource_visible(
    user: User,
    resource: ActiveResource,
    not_found_detail: str,
) -> None:
    """Скрывает неактивный ресурс от обычного пользователя."""
    if user.role == UserRole.USER and not resource.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=not_found_detail,
        )
