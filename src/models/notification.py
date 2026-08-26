import enum
import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, UUID, CheckConstraint, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_model import Base
from core.constants import NOTIFICATION_ERROR_MAX_LENGTH


class NotificationType(enum.StrEnum):
    """Типы уведомлений."""

    REMINDER_CLIENT = 'REMINDER_CLIENT'
    CREATED = 'CREATED'
    UPDATED = 'UPDATED'
    CANCELED = 'CANCELED'


class NotificationStatus(enum.StrEnum):
    """Статусы уведомлений."""

    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    SENT = 'SENT'
    FAILED = 'FAILED'
    CANCELED = 'CANCELED'


class BookingNotification(Base):
    """Модель уведомлений о бронировании стола."""

    __tablename__ = 'booking_notifications'

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            'bookings.id',
            name='fk_booking_id_booking_notifications',
            ondelete='CASCADE',
        ),
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name='booking_notification_type_enum'),
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name='booking_notification_status_enum'),
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING.value,
    )
    scheduled_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    last_error: Mapped[str | None] = mapped_column(
        String(NOTIFICATION_ERROR_MAX_LENGTH),
        nullable=True,
    )
    booking: Mapped['Booking'] = relationship(  # noqa: F821
        'Booking',
        back_populates='notifications',
        lazy='selectin',
    )

    __table_args__ = (
        Index(
            'unique_booking_notifications_booking_type',
            'booking_id',
            'type',
            unique=True,
            postgresql_where=text("status NOT IN ('CANCELED', 'FAILED')"),
        ),
        # Для штатной выборки очереди Beat-диспетчером
        Index(
            'ix_booking_notifications_pending_due',
            'scheduled_at',
            postgresql_where=text("status = 'PENDING'"),
        ),
        # Для поиска зависших задач
        Index(
            'ix_booking_notifications_stuck_recovery',
            'updated_at',
            postgresql_where=text("status = 'PROCESSING'"),
        ),
        CheckConstraint('attempts >= 0', name='check_attempts_non_negative'),
    )
