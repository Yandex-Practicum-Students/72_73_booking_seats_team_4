from exceptions.common import PermissionDeniedError
from models.user import User, UserRole


def is_admin(user: User) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user.role == UserRole.ADMIN


def ensure_user_update_allowed(
    actor: User,
    target_user: User,
    requested_role: UserRole | None,
) -> None:
    """Задает ограничения на редактирование данных пользователей.

    - Не позволяет менеджеру управлять администраторами.
    - Не позволяет администратору деактивировать администраторов.
    """
    if is_admin(actor) and is_admin(target_user):
        raise PermissionDeniedError(
            'Администратор не может деактивировать администратора или изменить его роль.',
        )
    if not is_admin(actor) and (is_admin(target_user) or requested_role == UserRole.ADMIN):
        raise PermissionDeniedError(
            'Менеджер не может изменять администратора или назначать эту роль.',
        )
