from exceptions.common import EntityNotFoundError


class ManagerNotFoundError(EntityNotFoundError):
    """Указанный менеджер не найден."""


class ManagerRoleError(Exception):
    """Указанный пользователь не является менеджером."""


class ManagerAlreadyAssignedError(Exception):
    """Менеджер уже привязан к другому кафе."""
