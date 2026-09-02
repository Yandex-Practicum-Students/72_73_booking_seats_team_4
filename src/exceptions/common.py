class EntityNotFoundError(Exception):
    """Сущность не найдена при выполнении бизнес-операции."""


class PermissionDeniedError(Exception):
    """Пользователю запрещено выполнять бизнес-операцию."""
