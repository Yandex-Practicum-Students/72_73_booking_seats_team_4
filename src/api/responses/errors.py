from fastapi import status

from core.errors import APIError


class BookingNotFoundError(APIError):
    """Бронирование не найдено."""

    def __init__(self) -> None:
        """Инициализирует ошибку отсутствующего бронирования."""
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message='Бронирование не найдено.',
        )


class BookingAlreadyExistsError(APIError):
    """Бронирование уже существует."""

    def __init__(self) -> None:
        """Инициализирует ошибку существующего бронирования."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Бронирование уже существует.',
        )


class CrossSlotsExistsError(APIError):
    """Существует бронирование с пересекающимися слотами."""

    def __init__(self) -> None:
        """Инициализирует ошибку пересекающихся слотов."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='У пользователя есть бронирования с пересекающимися слотами.',
        )
