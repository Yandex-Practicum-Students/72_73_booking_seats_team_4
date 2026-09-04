class UserAlreadyExistsError(ValueError):
    """Пользователь с одним из уникальных полей уже существует."""


class UserNotFoundError(LookupError):
    """Пользователь с переданным идентификатором не найден."""
