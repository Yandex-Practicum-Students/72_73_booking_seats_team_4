from models.user import User, UserRole
from services.errors import PermissionDeniedError


def is_admin(user: User) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user.role == UserRole.ADMIN


def ensure_user_update_allowed(
    actor: User,
    target_user: User,
    requested_role: UserRole | None,
) -> None:
    """Не позволяет менеджеру управлять администраторами."""
    if not is_admin(actor) and (
        is_admin(target_user) or requested_role == UserRole.ADMIN
    ):
        raise PermissionDeniedError(
            'Менеджер не может изменять администратора или назначать эту роль.',
        )
