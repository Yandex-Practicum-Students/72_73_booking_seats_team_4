from typing import Annotated

from fastapi import Depends, status

from api.dependencies.logging import set_me_user_logging_context, set_user_logging_context
from api.errors import APIError
from models.user import User, UserRole

CurrentUser = Annotated[User, Depends(set_user_logging_context)]
MeUser = Annotated[User, Depends(set_me_user_logging_context)]


def is_admin(user: User) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user.role == UserRole.ADMIN


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


def ensure_user_update_allowed(
    actor: User,
    target_user: User,
    requested_role: UserRole | None,
) -> None:
    """Не позволяет менеджеру управлять администраторами."""
    if not is_admin(actor) and (is_admin(target_user) or requested_role == UserRole.ADMIN):
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='Менеджер не может изменять администратора или назначать эту роль.',
        )
