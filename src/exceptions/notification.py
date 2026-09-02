from fastapi import status

from exceptions.base import APIError


class NotificationNotFoundError(APIError):
    """Уведомление не найдено в указанном бронировании."""

    def __init__(self) -> None:
        """Инициализирует ошибку отсутствующего уведомления."""
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message='Уведомление не найдено.',
        )


class NotificationRetryNotAllowedError(APIError):
    """Уведомление не находится в состоянии, допускающем повтор."""

    def __init__(self) -> None:
        """Инициализирует ошибку недопустимого повторного запуска."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Повторная отправка доступна только для уведомлений со статусом FAILED.',
        )
