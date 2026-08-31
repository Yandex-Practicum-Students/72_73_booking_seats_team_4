import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from models import NotificationStatus, NotificationType, StatusBooking  # noqa: E402
from services.notification import NotificationService  # noqa: E402
from tasks.base import shutdown_worker_event_loop  # noqa: E402
from tasks.channels.email import EmailChannel  # noqa: E402
from tasks.notifications import (  # noqa: E402
    _dispatch_notification,
    process_pending_due_notifications,
    send_booking_notification,
)


class AsyncSessionContext:
    """Минимальный async context manager для сессии задачи."""

    def __init__(self, session: AsyncMock) -> None:
        """Сохраняет тестовую сессию."""
        self.session = session

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *_: object) -> None:
        return None


def _make_notification(
    notification_type: NotificationType = NotificationType.CREATED,
) -> SimpleNamespace:
    """Создаёт уведомление с загруженным бронированием."""
    booking = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        booking_date=date.today() + timedelta(days=1),
        guest_number=2,
        note='У окна',
        status=StatusBooking.BOOKING,
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        booking_id=booking.id,
        booking=booking,
        type=notification_type,
        status=NotificationStatus.PENDING,
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        sent_at=None,
        sent_to=[],
    )


class CeleryNotificationTaskTests(TestCase):
    """Проверяет исполнение Celery-задач без внешнего брокера."""

    def tearDown(self) -> None:
        """Закрывает event loop, созданный синхронной обёрткой задачи."""
        shutdown_worker_event_loop()

    def test_send_task_dispatches_and_marks_notification_sent(self) -> None:
        """Задача вызывает канал и фиксирует успешную отправку."""
        session = AsyncMock(spec=AsyncSession)
        notification = _make_notification()
        get_for_processing = AsyncMock(return_value=notification)
        dispatch = AsyncMock()

        with (
            patch(
                'tasks.notifications.session_maker',
                return_value=AsyncSessionContext(session),
            ),
            patch(
                'tasks.notifications.notification_crud.get_for_processing',
                new=get_for_processing,
            ),
            patch(
                'tasks.notifications._dispatch_notification',
                new=dispatch,
            ),
        ):
            result = send_booking_notification.apply(
                args=(str(notification.id),),
                throw=True,
            )

        self.assertTrue(result.successful())
        get_for_processing.assert_awaited_once_with(
            notification.id,
            session,
        )
        dispatch.assert_awaited_once()
        self.assertEqual(notification.status, NotificationStatus.SENT)
        self.assertIsNotNone(notification.sent_at)
        session.commit.assert_awaited_once()

    def test_dispatcher_enqueues_every_due_notification(self) -> None:
        """Beat-диспетчер публикует отдельную задачу для каждого ID."""
        session = AsyncMock(spec=AsyncSession)
        notification_ids = [uuid.uuid4(), uuid.uuid4()]
        get_due = AsyncMock(return_value=notification_ids)
        delay = Mock()

        with (
            patch(
                'tasks.notifications.session_maker',
                return_value=AsyncSessionContext(session),
            ),
            patch(
                'tasks.notifications.notification_crud.get_due_notifications',
                new=get_due,
            ),
            patch(
                'tasks.notifications.send_booking_notification.delay',
                new=delay,
            ),
        ):
            result = process_pending_due_notifications.apply(
                args=(10,),
                throw=True,
            )

        self.assertTrue(result.successful())
        get_due.assert_awaited_once_with(session=session, limit=10)
        session.commit.assert_awaited_once()
        self.assertEqual(
            [call.args[0] for call in delay.call_args_list],
            [str(item) for item in notification_ids],
        )


class NotificationServiceTests(TestCase):
    """Проверяет расчёт времени напоминания."""

    def test_reminder_uses_earliest_booking_slot(self) -> None:
        """Напоминание планируется от раннего слота, а не от времени по умолчанию."""
        booking_date = date.today() + timedelta(days=2)
        booking = SimpleNamespace(
            booking_date=booking_date,
            tables_slots=[
                SimpleNamespace(slot=SimpleNamespace(start_time=time(15, 0))),
                SimpleNamespace(slot=SimpleNamespace(start_time=time(10, 30))),
            ],
        )
        service = NotificationService(session=AsyncMock(spec=AsyncSession))

        reminder_time = service._get_reminder_time(booking)

        self.assertEqual(
            reminder_time,
            datetime.combine(
                booking_date,
                time(7, 30, tzinfo=timezone.utc),
            ),
        )


class NotificationDispatchTests(IsolatedAsyncioTestCase):
    """Проверяет маршрутизацию писем клиентам и менеджерам."""

    async def test_client_reminder_is_sent_to_booking_owner(self) -> None:
        """Клиентское напоминание адресуется владельцу бронирования."""
        notification = _make_notification(NotificationType.REMINDER_CLIENT)
        channel = AsyncMock(spec=EmailChannel)
        session = AsyncMock(spec=AsyncSession)

        await _dispatch_notification(notification, channel, session)

        channel.send.assert_awaited_once()
        self.assertEqual(
            channel.send.await_args.kwargs['recipient_id'],
            notification.booking.user_id,
        )

    async def test_manager_notification_tracks_successful_recipients(self) -> None:
        """Успешно уведомлённые менеджеры сохраняются для идемпотентности."""
        notification = _make_notification()
        manager_ids = [uuid.uuid4(), uuid.uuid4()]
        channel = AsyncMock(spec=EmailChannel)
        session = AsyncMock(spec=AsyncSession)

        with patch(
            'tasks.notifications.booking_crud.get_managers_by_booking',
            new=AsyncMock(return_value=manager_ids),
        ):
            await _dispatch_notification(notification, channel, session)

        self.assertEqual(channel.send.await_count, 2)
        self.assertEqual(set(notification.sent_to), set(manager_ids))
        self.assertEqual(session.flush.await_count, 2)


class EmailChannelTests(IsolatedAsyncioTestCase):
    """Проверяет SMTP-канал без реального сетевого подключения."""

    async def test_channel_resolves_recipient_and_uses_configured_smtp(self) -> None:
        """Канал получает email из БД и передаёт настройки в aiosmtplib."""
        session = AsyncMock(spec=AsyncSession)
        recipient_id = uuid.uuid4()
        get_user = AsyncMock(
            return_value=SimpleNamespace(email='recipient@example.com'),
        )
        smtp_send = AsyncMock()
        channel = EmailChannel(
            session=session,
            smtp_host='smtp.example.com',
            smtp_port=465,
            smtp_user='sender@example.com',
            smtp_password='test-password',
            from_email='sender@example.com',
        )

        with (
            patch(
                'tasks.channels.email.user_crud.get_or_raise',
                new=get_user,
            ),
            patch('tasks.channels.email.aiosmtplib.send', new=smtp_send),
        ):
            await channel.send(
                recipient_id=recipient_id,
                subject='Бронирование',
                body='Стол забронирован',
            )

        get_user.assert_awaited_once_with(recipient_id, session)
        smtp_send.assert_awaited_once()
        self.assertEqual(
            smtp_send.await_args.kwargs,
            {
                'hostname': 'smtp.example.com',
                'port': 465,
                'username': 'sender@example.com',
                'password': 'test-password',
                'use_tls': True,
                'timeout': 10.0,
            },
        )

    async def test_channel_rejects_user_without_email(self) -> None:
        """Отсутствующий email даёт явную ошибку без обращения к SMTP."""
        session = AsyncMock(spec=AsyncSession)
        channel = EmailChannel(
            session=session,
            smtp_host='smtp.example.com',
            smtp_port=465,
            smtp_user='sender@example.com',
            smtp_password='test-password',
            from_email='sender@example.com',
        )
        smtp_send = AsyncMock()

        with (
            patch(
                'tasks.channels.email.user_crud.get_or_raise',
                new=AsyncMock(return_value=SimpleNamespace(email=None)),
            ),
            patch('tasks.channels.email.aiosmtplib.send', new=smtp_send),
        ):
            with self.assertRaisesRegex(ValueError, 'нет email'):
                await channel.send(
                    recipient_id=uuid.uuid4(),
                    subject='Бронирование',
                    body='Стол забронирован',
                )

        smtp_send.assert_not_awaited()
