from datetime import datetime, time, timedelta, timezone
from typing import Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.notification import NotificationCRUD, notification_crud
from models import Booking, BookingNotification, NotificationType, StatusBooking

REMINDER_MINUTES_BEFORE = 180
DEFAULT_BOOKING_TIME = time(12, 0, tzinfo=timezone.utc)


class NotificationService:
    """Сервис отправки уведомлений и напоминаний.

    - Уведомления менеджеру направляются сразу после создания, изменения, отмены брони
    - Напоминания гостю направляются за REMINDER_MINUTES_BEFORE до start_time самого раннего слота в брони

    - Использование в бизнес-логике

    ```python
    # При создании бронирования:
    notification_service = NotificationService(session)
    await notification_service.create_booking_notifications(booking)
    await session.commit()

    # При обновлении/отмене бронирования:
    await notification_service.update_booking_notifications(booking)
    await session.commit()
    ```
    """

    def __init__(
        self,
        session: AsyncSession,
        notification_crud: NotificationCRUD = notification_crud,
    ) -> None:
        """Настройки экземпляра сервиса."""
        self.session = session
        self.notification_crud = notification_crud

    def _get_reminder_time(
        self,
        booking: Booking,
        minutes_before: int = REMINDER_MINUTES_BEFORE,
    ) -> datetime:
        """Расчёт времени напоминания за N минут до начала визита."""
        earliest_time = DEFAULT_BOOKING_TIME

        table_slots = getattr(booking, 'table_slot', None) or []
        start_times = [
            table_slot.slot.start_time
            for table_slot in table_slots
            if getattr(table_slot, 'slot', None) and table_slot.slot.start_time is not None
        ]
        if start_times:
            earliest_time = min(start_times)

        if earliest_time.tzinfo is None:
            earliest_time = earliest_time.replace(tzinfo=timezone.utc)

        booking_dt = datetime.combine(booking.booking_date, earliest_time).astimezone(timezone.utc)
        reminder_time = booking_dt - timedelta(minutes=minutes_before)

        return max(reminder_time, datetime.now(timezone.utc))

    async def create_booking_notifications(self, booking: Booking) -> None:
        """Уведомление + напоминание при создании бронирования."""
        manager_notification = await self.notification_crud.create_for_booking(
            booking_id=booking.id,
            type_=NotificationType.CREATED,
            scheduled_at=datetime.now(timezone.utc),
            session=self.session,
        )

        client_reminder = await self.notification_crud.create_for_booking(
            booking_id=booking.id,
            type_=NotificationType.REMINDER_CLIENT,
            scheduled_at=self._get_reminder_time(booking),
            session=self.session,
        )

        logger.info(
            'Для бронирования {id} созданы уведомление менеджеру {notification} '
            'и напоминание клиенту {reminder}',
            id=booking.id,
            notification=manager_notification.id,
            reminder=client_reminder.id,
        )

    async def update_booking_notifications(self, booking: Booking) -> None:
        """Уведомление + напоминание при изменении бронирования."""
        now = datetime.now(timezone.utc)

        await self.notification_crud.cancel_pending_for_booking(
            booking_id=booking.id,
            session=self.session,
        )

        client_reminder: Optional[BookingNotification] = None

        if booking.status == StatusBooking.CANCELED:
            manager_notification = await self.notification_crud.create_for_booking(
                booking_id=booking.id,
                type_=NotificationType.CANCELED,
                scheduled_at=now,
                session=self.session,
            )
        else:
            manager_notification = await self.notification_crud.create_for_booking(
                booking_id=booking.id,
                type_=NotificationType.UPDATED,
                scheduled_at=now,
                session=self.session,
            )
            client_reminder = await self.notification_crud.create_for_booking(
                booking_id=booking.id,
                type_=NotificationType.REMINDER_CLIENT,
                scheduled_at=self._get_reminder_time(booking),
                session=self.session,
            )

        logger.info(
            'Для измененного бронирования {id} созданы уведомление менеджеру {notification} '
            'и напоминание клиенту (опционально) {reminder}',
            id=booking.id,
            notification=manager_notification.id,
            reminder=client_reminder.id if client_reminder else 'Отсутствует/Отмена брони',
        )
