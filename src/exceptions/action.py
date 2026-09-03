from exceptions.base import APIError


class ActionAlreadyExistsError(ValueError):
    """Акция с таким описанием уже существует."""


class CafeActionAlreadyExistsError(APIError):
    """Одна и та же акция не может повторяться в одном и том же кафе."""


class PhotoError(APIError):
    """Такого фото не существует."""
