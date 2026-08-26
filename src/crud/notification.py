import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import BookingNotification, NotificationStatus, NotificationType
from schemas.notification import BookingNotificationCreate


class NotificationCRUD:
    """CRUD для уведомлений о бронировании.

    ВАЖНО: для атомарности коммитит вызывающая сторона BookingService.
    """

    def __init__(self) -> None:
        """Настройки экземпляра."""
        self.model = BookingNotification

    async def create(
        self,
        obj_in: BookingNotificationCreate,
        session: AsyncSession,
    ) -> BookingNotification:
        """Создать уведомление."""
        notification = self.model(
            booking_id=obj_in.booking_id,
            type=obj_in.type,
            status=NotificationStatus.PENDING,
            scheduled_at=obj_in.scheduled_at,
            attempts=0,
        )
        session.add(notification)
        await session.flush()
        return notification

    async def create_for_booking(
        self,
        booking_id: uuid.UUID,
        type_: NotificationType,
        scheduled_at: datetime,
        session: AsyncSession,
    ) -> BookingNotification:
        """Создать уведомление для бронирования."""
        obj_in = BookingNotificationCreate(
            booking_id=booking_id,
            type=type_,
            scheduled_at=scheduled_at,
        )
        return await self.create(obj_in, session)

    async def cancel_pending_for_booking(
        self,
        booking_id: uuid.UUID,
        session: AsyncSession,
    ) -> None:
        """Пометить все PENDING уведомления бронирования как CANCELED."""
        await session.execute(
            update(self.model)
            .where(
                self.model.booking_id == booking_id,
                self.model.status == NotificationStatus.PENDING,
            )
            .values(status=NotificationStatus.CANCELED),
        )

    async def get_due_notifications(
        self,
        session: AsyncSession,
        limit: int = 100,
        stuck_timeout_minutes: int = 10,
    ) -> Sequence[uuid.UUID]:
        """Атомарно выбирает PENDING и зависшие PROCESSING уведомления.

        Переводит их в статус PROCESSING с защитой от параллельных воркеров.
        """
        now = datetime.now(timezone.utc)
        stuck_threshold = now - timedelta(minutes=stuck_timeout_minutes)

        subquery = (
            select(self.model.id)
            .where(
                or_(
                    (self.model.status == NotificationStatus.PENDING) & (self.model.scheduled_at <= now),
                    (self.model.status == NotificationStatus.PROCESSING)
                    & (self.model.updated_at <= stuck_threshold),
                ),
            )
            .order_by(self.model.scheduled_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )

        stmt = (
            update(self.model)
            .where(self.model.id.in_(subquery))
            .values(
                status=NotificationStatus.PROCESSING,
                updated_at=now,
            )
            .returning(self.model.id)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_for_processing(
        self,
        notification_id: uuid.UUID,
        session: AsyncSession,
    ) -> Optional[BookingNotification]:
        """Получить уведомление с блокировкой строки для безопасной отправки."""
        query = (
            select(self.model)
            .options(selectinload(self.model.booking))
            .where(self.model.id == notification_id)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def mark_sent(
        self,
        notification: BookingNotification,
    ) -> None:
        """Пометить уведомление как отправленное."""
        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.now(timezone.utc)

    async def increment_attempts(
        self,
        notification: BookingNotification,
        error: str,
        max_attempts: int = 3,
    ) -> None:
        """Увеличить счётчик попыток и, при необходимости, пометить как FAILED."""
        notification.attempts += 1
        notification.last_error = error

        if notification.attempts >= max_attempts:
            notification.status = NotificationStatus.FAILED
        else:
            notification.status = NotificationStatus.PENDING


notification_crud = NotificationCRUD()
