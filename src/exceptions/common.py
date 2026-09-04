class EntityNotFoundError(Exception):
    """Сущность не найдена при выполнении бизнес-операции."""


class PermissionDeniedError(Exception):
    """Пользователю запрещено выполнять бизнес-операцию."""


class BadRequestError(ValueError):
    """Ошибка передачи пользователем полей с некорректными значениями."""
