import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.logging import get_current_user_with_logging
from api.errors import APIError
from crud.notification import NotificationCRUD
from main import app
from models import NotificationStatus, NotificationType
from models.user import UserRole
from services.booking import BookingService
from services.dependencies import (
    get_booking_service,
    get_notification_service,
)
from services.notification import (
    NotificationRetryNotAllowedError,
    NotificationService,
)

from core.db import get_session


def _make_user(
    role: UserRole,
    *,
    user_id: uuid.UUID | None = None,
    cafe_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    """Создаёт пользователя для dependency override."""
    return SimpleNamespace(
        id=user_id or uuid.uuid4(),
        username=f'{role.value.lower()}-notification-tester',
        email=f'{role.value.lower()}@example.com',
        phone=None,
        tg_id=None,
        role=role,
        cafe_id=cafe_id,
    )


def _make_notification(
    booking_id: uuid.UUID,
    *,
    notification_id: uuid.UUID | None = None,
    status_: NotificationStatus = NotificationStatus.PENDING,
    type_: NotificationType = NotificationType.CREATED,
) -> SimpleNamespace:
    """Создаёт объект, совместимый с BookingNotificationInfo."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=notification_id or uuid.uuid4(),
        booking_id=booking_id,
        type=type_,
        status=status_,
        scheduled_at=now,
        sent_at=None,
        attempts=0,
        last_error=None,
        sent_to=[],
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class NotificationAPITests(IsolatedAsyncioTestCase):
    """Проверяет API статусов и ручного повтора уведомлений."""

    async def asyncSetUp(self) -> None:
        """Подменяет внешние зависимости и создаёт ASGI-клиент."""
        app.dependency_overrides.clear()
        self.session = AsyncMock(spec=AsyncSession)

        async def session_override() -> AsyncGenerator[AsyncSession, None]:
            yield self.session

        app.dependency_overrides[get_session] = session_override
        self.booking_service = AsyncMock(spec=BookingService)
        self.notification_service = AsyncMock(spec=NotificationService)
        app.dependency_overrides[get_booking_service] = lambda: self.booking_service
        app.dependency_overrides[get_notification_service] = lambda: self.notification_service
        self._set_user(_make_user(UserRole.ADMIN))
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        )

    async def asyncTearDown(self) -> None:
        """Закрывает клиент и очищает dependency overrides."""
        await self.client.aclose()
        app.dependency_overrides.clear()

    def _set_user(self, user: SimpleNamespace) -> None:
        """Подменяет текущего пользователя."""

        async def user_override() -> AsyncGenerator[SimpleNamespace, None]:
            yield user

        app.dependency_overrides[get_current_user_with_logging] = user_override

    async def test_list_returns_filtered_notification_statuses(self) -> None:
        """Список проверяет доступ к брони и передаёт фильтры в сервис."""
        booking_id = uuid.uuid4()
        booking = SimpleNamespace(id=booking_id)
        notification = _make_notification(
            booking_id,
            status_=NotificationStatus.FAILED,
            type_=NotificationType.REMINDER_CLIENT,
        )
        self.booking_service.get_booking_or_raise.return_value = booking
        self.notification_service.get_booking_notifications.return_value = [
            notification,
        ]

        response = await self.client.get(
            f'/api/v1/booking/{booking_id}/notifications',
            params={
                'type': NotificationType.REMINDER_CLIENT.value,
                'status': NotificationStatus.FAILED.value,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(notification.id))
        self.assertNotIn('last_error', response.json()[0])
        self.assertNotIn('sent_to', response.json()[0])
        self.booking_service.check_user_permission.assert_awaited_once()
        self.notification_service.get_booking_notifications.assert_awaited_once_with(
            booking_id=booking_id,
            type_=NotificationType.REMINDER_CLIENT,
            status_=NotificationStatus.FAILED,
        )

    async def test_detail_requires_access_to_booking(self) -> None:
        """Запрет на просмотр брони применяется и к её уведомлениям."""
        booking_id = uuid.uuid4()
        notification_id = uuid.uuid4()
        self.booking_service.get_booking_or_raise.return_value = SimpleNamespace(
            id=booking_id,
        )
        self.booking_service.check_user_permission.side_effect = APIError(
            status_code=403,
            message='Доступ запрещен.',
        )

        response = await self.client.get(
            f'/api/v1/booking/{booking_id}/notifications/{notification_id}',
        )

        self.assertEqual(response.status_code, 403)
        self.notification_service.get_notification_or_raise.assert_not_awaited()

    async def test_regular_user_cannot_retry_notification(self) -> None:
        """Ручной повтор недоступен обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        booking_id = uuid.uuid4()
        notification_id = uuid.uuid4()

        response = await self.client.post(
            f'/api/v1/booking/{booking_id}/notifications/{notification_id}/retry',
        )

        self.assertEqual(response.status_code, 403)
        self.notification_service.retry_failed_notification.assert_not_awaited()

    async def test_manager_retries_failed_notification_in_own_cafe(self) -> None:
        """Менеджер может вернуть FAILED-уведомление своей брони в очередь."""
        cafe_id = uuid.uuid4()
        manager = _make_user(UserRole.MANAGER, cafe_id=cafe_id)
        self._set_user(manager)
        booking_id = uuid.uuid4()
        booking = SimpleNamespace(id=booking_id, cafe_id=cafe_id)
        notification = _make_notification(
            booking_id,
            status_=NotificationStatus.PENDING,
        )
        self.booking_service.get_booking_or_raise.return_value = booking
        self.notification_service.retry_failed_notification.return_value = notification
        enqueue = Mock()

        with patch(
            'api.endpoints.notification.send_booking_notification.delay',
            new=enqueue,
        ):
            response = await self.client.post(
                f'/api/v1/booking/{booking_id}/notifications/{notification.id}/retry',
            )

        self.assertEqual(response.status_code, 202)
        self.booking_service.check_user_permission.assert_awaited_once_with(
            booking=booking,
            user=manager,
        )
        self.notification_service.retry_failed_notification.assert_awaited_once_with(
            booking_id=booking_id,
            notification_id=notification.id,
        )
        enqueue.assert_called_once_with(str(notification.id))


class NotificationRetryServiceTests(IsolatedAsyncioTestCase):
    """Проверяет безопасный перевод FAILED-уведомления в очередь."""

    def setUp(self) -> None:
        """Создаёт сервис с моками БД и CRUD."""
        self.session = Mock(spec=AsyncSession)
        self.session.add = Mock()
        self.session.commit = AsyncMock()
        self.session.refresh = AsyncMock()
        self.crud = AsyncMock(spec=NotificationCRUD)
        self.service = NotificationService(
            session=self.session,
            notification_crud=self.crud,
        )

    async def test_retry_resets_failure_and_preserves_sent_recipients(self) -> None:
        """Ручной повтор очищает ошибку, но не дублирует успешные письма."""
        booking_id = uuid.uuid4()
        sent_manager_id = uuid.uuid4()
        notification = _make_notification(
            booking_id,
            status_=NotificationStatus.FAILED,
        )
        notification.attempts = 3
        notification.last_error = 'SMTP unavailable'
        notification.sent_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        notification.sent_to = [sent_manager_id]
        self.crud.get_by_id_for_booking.return_value = notification

        result = await self.service.retry_failed_notification(
            booking_id=booking_id,
            notification_id=notification.id,
        )

        self.assertIs(result, notification)
        self.assertEqual(notification.status, NotificationStatus.PENDING)
        self.assertEqual(notification.attempts, 0)
        self.assertIsNone(notification.last_error)
        self.assertIsNone(notification.sent_at)
        self.assertEqual(notification.sent_to, [sent_manager_id])
        self.session.add.assert_called_once_with(notification)
        self.session.commit.assert_awaited_once()
        self.session.refresh.assert_awaited_once_with(notification)
        self.crud.get_by_id_for_booking.assert_awaited_once_with(
            notification_id=notification.id,
            booking_id=booking_id,
            session=self.session,
            for_update=True,
        )

    async def test_retry_rejects_notification_that_is_not_failed(self) -> None:
        """Повтор PENDING или SENT уведомления не создаёт дубликат задачи."""
        booking_id = uuid.uuid4()
        notification = _make_notification(booking_id)
        self.crud.get_by_id_for_booking.return_value = notification

        with self.assertRaises(NotificationRetryNotAllowedError):
            await self.service.retry_failed_notification(
                booking_id=booking_id,
                notification_id=notification.id,
            )

        self.session.commit.assert_not_awaited()
