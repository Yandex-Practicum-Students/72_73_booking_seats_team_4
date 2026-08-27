class EntityNotFoundError(Exception):
    """Сущность не найдена при выполнении бизнес-операции."""


class PermissionDeniedError(Exception):
    """Пользователю запрещено выполнять бизнес-операцию."""


class ManagerNotFoundError(EntityNotFoundError):
    """Указанный менеджер не найден."""


class ManagerRoleError(Exception):
    """Указанный пользователь не является менеджером."""


class ManagerAlreadyAssignedError(Exception):
    """Менеджер уже привязан к другому кафе."""
