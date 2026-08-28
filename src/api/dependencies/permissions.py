from typing import Annotated

from fastapi import Depends, status

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
