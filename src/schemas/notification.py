import uuid
from datetime import datetime

from pydantic import Field

from models import NotificationStatus, NotificationType
from schemas.base import BaseInfoScheme, IdScheme


class BookingNotificationInfo(IdScheme, BaseInfoScheme):
    """Публичный статус уведомления или напоминания о бронировании."""

    booking_id: uuid.UUID
    type: NotificationType
    status: NotificationStatus
    scheduled_at: datetime
    sent_at: datetime | None
    attempts: int = Field(ge=0)
