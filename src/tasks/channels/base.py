from abc import ABC, abstractmethod
from uuid import UUID


class NotificationChannel(ABC):
    """Абстракция канала отправки уведомлений."""

    @abstractmethod
    async def send(self, recipient_id: UUID, subject: str, body: str) -> None:
        """Отправка уведомления получателю.

        Параметры:
            recipient_id: UUID получателя (user_id)
            subject: Тема уведомления (для email) или заголовок
            body: Тело сообщения
        """
        pass
