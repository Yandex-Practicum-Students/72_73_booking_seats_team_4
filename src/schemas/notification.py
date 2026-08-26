import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.notification import NotificationStatus, NotificationType


class BookingNotificationBase(BaseModel):
    """Базовая схема уведомления."""

    type: NotificationType
    scheduled_at: datetime


class BookingNotificationCreate(BookingNotificationBase):
    """Схема создания уведомления."""

    booking_id: uuid.UUID


class BookingNotificationUpdate(BaseModel):
    """Схема обновления уведомления."""

    status: NotificationStatus | None = None
    sent_at: datetime | None = None
    attempts: int | None = Field(None, ge=0)
    last_error: str | None = None


class BookingNotificationSchema(BookingNotificationBase):
    """Схема ответа по уведомлению."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID
    status: NotificationStatus
    sent_at: datetime | None
    attempts: int
    last_error: str | None
