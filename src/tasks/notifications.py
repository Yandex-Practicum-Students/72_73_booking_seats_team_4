import uuid
from datetime import datetime, timezone
from typing import Sequence

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.booking import booking_crud
from crud.notification import notification_crud
from models import BookingNotification, NotificationStatus, NotificationType, StatusBooking
from tasks import celery_app
from tasks.base import RetryableTask, async_task
from tasks.channels.email import EmailChannel

from core.db import session_maker
from core.settings import settings


@celery_app.task(
    base=RetryableTask,
    name='booking.notifications.send_notification',
    bind=True,
    no_retry_exceptions=(ValueError,),
)
@async_task
async def send_booking_notification(self: RetryableTask, notification_id: str | uuid.UUID) -> None:
    """Отправка одного уведомления (клиенту или менеджеру)."""
    if isinstance(notification_id, str):
        notification_id = uuid.UUID(notification_id)

    async with session_maker() as session:
        notification = await notification_crud.get_for_processing(notification_id, session)

        if notification is None:
            logger.warning('Уведомление {id} не найдено или заблокировано, пропускаем', id=notification_id)
            return

        if notification.status not in (NotificationStatus.PENDING, NotificationStatus.PROCESSING):
            logger.info('Бронирование {id} не готово к отправке', id=notification.booking_id)
            return

        if notification.scheduled_at > datetime.now(timezone.utc):
            logger.info('Уведомление {id} запланировано на будущее, откладываем', id=notification.id)
            notification.status = NotificationStatus.PENDING
            await session.commit()
            return

        if (
            notification.type == NotificationType.REMINDER_CLIENT
            and notification.booking.status == StatusBooking.CANCELED
        ):
            logger.info(
                'Бронирование {id} отменено, отменяем напоминание',
                id=notification.booking_id,
            )
            notification.status = NotificationStatus.CANCELED
            await session.commit()
            return

        channel = EmailChannel(
            session=session,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            from_email=settings.smtp_from_email,
        )

        try:
            await _dispatch_notification(notification, channel, session)
        except Exception as error:
            await notification_crud.increment_attempts(
                notification=notification,
                error=str(error),
                session=session,
            )
            await session.commit()
            raise error

        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.now(timezone.utc)
        await session.commit()

        logger.info(
            'Уведомление {id} ({type}) успешно отправлено',
            id=notification.id,
            type=notification.type,
        )


@celery_app.task(name='booking.notifications.process_pending_due_notifications')
@async_task
async def process_pending_due_notifications(limit: int = 100) -> None:
    """Безопасный Beat-диспетчер с атомарным захватом записей.

    Периодическая отправка напоминаний гостям через планировщик.
    """
    async with session_maker() as session:
        notification_ids: Sequence[uuid.UUID] = await notification_crud.get_due_notifications(
            session=session,
            limit=limit,
        )
        await session.commit()

    for notification_id in notification_ids:
        send_booking_notification.delay(str(notification_id))


async def _dispatch_notification(
    notification: BookingNotification,
    channel: EmailChannel,
    session: AsyncSession,
) -> None:
    """Маршрутизация сообщения по целевой аудитории (Гость / Менеджер)."""
    booking = notification.booking

    if notification.type == NotificationType.REMINDER_CLIENT:
        subject = f'Напоминание о бронировании на {booking.booking_date}'
        body = (
            f'Здравствуйте! Напоминаем о вашем бронировании на {booking.booking_date}\n'
            f'(столик на {booking.guest_number} чел.).'
        )
        await channel.send(recipient_id=booking.user_id, subject=subject, body=body)
        return

    managers_ids = await booking_crud.get_managers_by_booking(booking.id, session)

    if not managers_ids:
        logger.warning(
            'Для бронирования {booking_id} не найдены менеджеры кафе для уведомления {notification_id}',
            booking_id=booking.id,
            notification_id=notification.id,
        )
        return

    already_sent = set(notification.sent_to or [])
    pending_ids = [manager_id for manager_id in managers_ids if manager_id not in already_sent]

    if not pending_ids:
        return

    subject = f'Бронирование #{booking.id}: статус {notification.type}'
    body = (
        f'Событие: {notification.type}\n'
        f'ID Бронирования: {booking.id}\n'
        f'Дата: {booking.booking_date}\n'
        f'Количество гостей: {booking.guest_number}\n'
        f'Комментарий: {booking.note or "-"}'
    )

    failed: list[tuple[uuid.UUID, Exception]] = []

    for manager_id in pending_ids:
        try:
            await channel.send(recipient_id=manager_id, subject=subject, body=body)
        except Exception as error:
            logger.error(
                'Ошибка отправки менеджеру {manager}: {error}',
                manager=manager_id,
                error=error,
            )
            failed.append((manager_id, error))
        else:
            already_sent.add(manager_id)
            notification.sent_to = list(already_sent)
            await session.flush()

    if failed:
        err = f'Не удалось отправить {len(failed)} сообщений менеджерам'
        raise RuntimeError(err)
