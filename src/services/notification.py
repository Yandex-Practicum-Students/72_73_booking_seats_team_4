import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from fastapi import status
from loguru import logger

from crud.notification import NotificationCRUD, notification_crud
from models import (
    Booking,
    BookingNotification,
    NotificationStatus,
    NotificationType,
    StatusBooking,
)

from core.db import DBSession
from core.errors import APIError

REMINDER_MINUTES_BEFORE = 180
DEFAULT_BOOKING_TIME = time(12, 0, tzinfo=timezone.utc)


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


class NotificationService:
    """Сервис отправки уведомлений и напоминаний.

    - Уведомления менеджеру направляются сразу после создания, изменения, отмены брони
    - Напоминания гостю направляются за настроенное в брони число минут
      до start_time самого раннего слота

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
        session: DBSession,
        notification_crud: NotificationCRUD = notification_crud,
    ) -> None:
        """Настройки экземпляра сервиса."""
        self.session = session
        self.notification_crud = notification_crud

    async def get_booking_notifications(
        self,
        booking_id: uuid.UUID,
        type_: NotificationType | None = None,
        status_: NotificationStatus | None = None,
    ) -> list[BookingNotification]:
        """Возвращает историю уведомлений и напоминаний бронирования."""
        notifications = await self.notification_crud.get_for_booking(
            booking_id=booking_id,
            session=self.session,
            type_=type_,
            status_=status_,
        )
        return list(notifications)

    async def get_notification_or_raise(
        self,
        booking_id: uuid.UUID,
        notification_id: uuid.UUID,
        for_update: bool = False,
    ) -> BookingNotification:
        """Возвращает уведомление бронирования или сообщает об отсутствии."""
        notification = await self.notification_crud.get_by_id_for_booking(
            notification_id=notification_id,
            booking_id=booking_id,
            session=self.session,
            for_update=for_update,
        )
        if notification is None:
            raise NotificationNotFoundError
        return notification

    async def retry_failed_notification(
        self,
        booking_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> BookingNotification:
        """Возвращает FAILED-уведомление в очередь для ручной отправки."""
        notification = await self.get_notification_or_raise(
            booking_id=booking_id,
            notification_id=notification_id,
            for_update=True,
        )
        if notification.status != NotificationStatus.FAILED:
            raise NotificationRetryNotAllowedError

        notification.status = NotificationStatus.PENDING
        notification.scheduled_at = datetime.now(timezone.utc)
        notification.sent_at = None
        notification.attempts = 0
        notification.last_error = None
        # sent_to намеренно сохраняется: уже получившие письмо менеджеры
        # не должны получить его повторно при частичном сбое рассылки.
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        logger.info(
            'Уведомление {id} возвращено в очередь вручную',
            id=notification.id,
        )
        return notification

    def _get_reminder_time(
        self,
        booking: Booking,
    ) -> datetime:
        """Расчёт времени напоминания за N минут до начала визита."""
        minutes_before = getattr(
            booking,
            'reminder_minutes_before',
            REMINDER_MINUTES_BEFORE,
        )
        if minutes_before is None:
            raise ValueError('Напоминание для бронирования отключено.')

        earliest_time = DEFAULT_BOOKING_TIME

        table_slots = getattr(booking, 'tables_slots', None) or []
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

    async def create_booking_notifications(
        self,
        booking: Booking,
    ) -> tuple[BookingNotification, BookingNotification | None]:
        """Уведомление + напоминание при создании бронирования."""
        manager_notification = await self.notification_crud.create_for_booking(
            booking_id=booking.id,
            type_=NotificationType.CREATED,
            scheduled_at=datetime.now(timezone.utc),
            session=self.session,
        )

        client_reminder: BookingNotification | None = None
        if getattr(booking, 'reminder_minutes_before', REMINDER_MINUTES_BEFORE) is not None:
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
            reminder=client_reminder.id if client_reminder else 'Отключено',
        )

        return manager_notification, client_reminder

    async def update_booking_notifications(
        self,
        booking: Booking,
    ) -> tuple[BookingNotification, BookingNotification | None]:
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
            if getattr(booking, 'reminder_minutes_before', REMINDER_MINUTES_BEFORE) is not None:
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

        return manager_notification, client_reminder or None
