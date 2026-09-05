from fastapi import status

from exceptions.base import APIError


class SlotOverlapError(APIError):
    """Попытка создать слот, пересекающийся по времени с существующим."""

    def __init__(self) -> None:
        """Инициализирует ошибку пересечения слотов."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Слот пересекается по времени с существующим слотом кафе.',
        )
