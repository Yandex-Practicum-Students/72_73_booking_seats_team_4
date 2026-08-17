from typing import Annotated

from fastapi import Depends, HTTPException, status

from models.user import User, UserRole

from core.user import get_current_user, get_current_user_or_forbidden

CurrentUser = Annotated[User, Depends(get_current_user)]
MeUser = Annotated[User, Depends(get_current_user_or_forbidden)]


def is_admin(user: User) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user.role == UserRole.ADMIN


async def get_staff_user(user: CurrentUser) -> User:
    """Разрешает доступ администраторам и менеджерам."""
    if user.role in (UserRole.ADMIN, UserRole.MANAGER):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Доступ запрещён.',
    )


async def get_admin_user(user: CurrentUser) -> User:
    """Разрешает доступ только администраторам."""
    if is_admin(user):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Доступ запрещён.',
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Менеджер не может изменять администратора или назначать эту роль.',
        )
