import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.booking import get_booking_service
from api.dependencies.logging import get_current_user_with_logging
from exceptions.base import APIError
from main import app
from models.booking import StatusBooking
from models.user import UserRole
from schemas.booking import BookingCreate, BookingTableSlot, BookingUpdate
from services.booking import BookingService

from core.db import get_session
from core.redis import get_redis_session


def _make_user(
    role: UserRole,
    *,
    user_id: uuid.UUID | None = None,
    cafe_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    """Создаёт пользователя нужной роли для dependency override."""
    return SimpleNamespace(
        id=user_id or uuid.uuid4(),
        username=f'{role.value.lower()}-tester',
        email=f'{role.value.lower()}@example.com',
        phone=None,
        tg_id=None,
        role=role,
        cafe_id=cafe_id,
    )


def _make_booking(
    *,
    booking_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    cafe_id: uuid.UUID | None = None,
    booking_date: date | None = None,
    guest_number: int = 2,
    note: str | None = 'Стол у окна',
    status: StatusBooking = StatusBooking.BOOKING,
    is_active: bool = True,
    reminder_minutes_before: int | None = 180,
) -> SimpleNamespace:
    """Создаёт объект, совместимый с BookingInfo."""
    booking_user = _make_user(UserRole.USER, user_id=user_id)
    cafe_id = cafe_id or uuid.uuid4()
    cafe = SimpleNamespace(
        id=cafe_id,
        name='Тестовое кафе',
        address='Москва, Тестовая улица, 1',
        phone='+79991234567',
        description='Кафе для API тестов',
        photo_id=None,
    )
    table = SimpleNamespace(
        id=uuid.uuid4(),
        seat_number=4,
        description='Стол у окна',
    )
    slot = SimpleNamespace(
        id=uuid.uuid4(),
        start_time=time(12, 0),
        end_time=time(13, 0),
        description='Обед',
    )
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=booking_id or uuid.uuid4(),
        user_id=booking_user.id,
        user=booking_user,
        cafe_id=cafe_id,
        cafe=cafe,
        booking_date=booking_date or date.today() + timedelta(days=1),
        guest_number=guest_number,
        note=note,
        status=status,
        reminder_minutes_before=reminder_minutes_before,
        tables_slots=[SimpleNamespace(table=table, slot=slot)],
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def _booking_payload(booking: SimpleNamespace) -> dict[str, object]:
    """Формирует валидное тело запроса на создание бронирования."""
    table_slot = booking.tables_slots[0]
    return {
        'cafe_id': str(booking.cafe_id),
        'booking_date': booking.booking_date.isoformat(),
        'guest_number': booking.guest_number,
        'note': booking.note,
        'reminder_minutes_before': booking.reminder_minutes_before,
        'tables_slots': [
            {
                'table_id': str(table_slot.table.id),
                'slot_id': str(table_slot.slot.id),
            },
        ],
    }


class BookingAPIContractTests(TestCase):
    """Проверяет опубликованный контракт ручек бронирований."""

    def test_booking_routes_match_specification(self) -> None:
        """Коллекция и отдельная бронь публикуют только заявленные методы."""
        paths = app.openapi()['paths']

        self.assertEqual(set(paths['/api/v1/booking']), {'get', 'post'})
        self.assertEqual(set(paths['/api/v1/booking/{booking_id}']), {'get', 'patch'})


class BookingAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP контракт и бизнес ограничения ручек /booking."""

    async def asyncSetUp(self) -> None:
        """Подменяет внешние зависимости и создаёт ASGI клиент."""
        app.dependency_overrides.clear()
        self.session = AsyncMock(spec=AsyncSession)

        async def session_override() -> AsyncGenerator[AsyncSession, None]:
            yield self.session

        async def redis_override() -> AsyncGenerator[AsyncMock, None]:
            yield AsyncMock()

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_redis_session] = redis_override
        self.booking_service = AsyncMock(spec=BookingService)
        app.dependency_overrides[get_booking_service] = lambda: self.booking_service
        self.current_user = _make_user(UserRole.ADMIN)
        self._set_user(self.current_user)
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        )

    async def asyncTearDown(self) -> None:
        """Закрывает клиент и очищает глобальные overrides приложения."""
        await self.client.aclose()
        app.dependency_overrides.clear()

    def _set_user(self, user: SimpleNamespace) -> None:
        """Подменяет текущего пользователя для следующего запроса."""
        self.current_user = user

        async def user_override() -> AsyncGenerator[SimpleNamespace, None]:
            yield user

        app.dependency_overrides[get_current_user_with_logging] = user_override

    async def test_list_requires_authentication(self) -> None:
        """Неавторизованный запрос не доходит до CRUD."""
        app.dependency_overrides.pop(get_current_user_with_logging)
        get_all = AsyncMock()

        with patch('api.endpoints.booking.booking_crud.get_all', new=get_all):
            response = await self.client.get('/api/v1/booking')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                'code': 401,
                'message': 'Не удалось проверить данные авторизации.',
            },
        )
        get_all.assert_not_awaited()

    async def test_admin_list_passes_all_filters_to_crud(self) -> None:
        """Администратор управляет всеми доступными фильтрами списка."""
        cafe_id = uuid.uuid4()
        user_id = uuid.uuid4()
        booking = _make_booking(cafe_id=cafe_id, user_id=user_id, is_active=False)
        get_all = AsyncMock(return_value=[booking])

        with patch('api.endpoints.booking.booking_crud.get_all', new=get_all):
            response = await self.client.get(
                '/api/v1/booking',
                params={
                    'show_active': 'false',
                    'cafe_id': str(cafe_id),
                    'user_id': str(user_id),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(booking.id))
        get_all.assert_awaited_once_with(
            session=self.session,
            show_active=False,
            cafe_id=cafe_id,
            user_id=user_id,
        )

    async def test_regular_user_is_limited_to_own_active_bookings(self) -> None:
        """USER не может снять фильтры своего id и активности."""
        user = _make_user(UserRole.USER)
        requested_user_id = uuid.uuid4()
        cafe_id = uuid.uuid4()
        booking = _make_booking(user_id=user.id, cafe_id=cafe_id)
        self._set_user(user)
        get_all = AsyncMock(return_value=[booking])

        with patch('api.endpoints.booking.booking_crud.get_all', new=get_all):
            response = await self.client.get(
                '/api/v1/booking',
                params={
                    'show_active': 'false',
                    'cafe_id': str(cafe_id),
                    'user_id': str(requested_user_id),
                },
            )

        self.assertEqual(response.status_code, 200)
        get_all.assert_awaited_once_with(
            session=self.session,
            show_active=True,
            cafe_id=cafe_id,
            user_id=user.id,
        )

    async def test_manager_is_limited_to_assigned_cafe(self) -> None:
        """MANAGER всегда получает брони только своего кафе."""
        own_cafe_id = uuid.uuid4()
        manager = _make_user(UserRole.MANAGER, cafe_id=own_cafe_id)
        self._set_user(manager)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.booking.booking_crud.get_all', new=get_all):
            response = await self.client.get(
                '/api/v1/booking',
                params={'cafe_id': str(uuid.uuid4())},
            )

        self.assertEqual(response.status_code, 200)
        get_all.assert_awaited_once_with(
            session=self.session,
            show_active=True,
            cafe_id=own_cafe_id,
            user_id=None,
        )

    async def test_manager_can_explicitly_request_inactive_bookings(self) -> None:
        """Явный show_active=false менеджера не перезаписывается."""
        own_cafe_id = uuid.uuid4()
        manager = _make_user(UserRole.MANAGER, cafe_id=own_cafe_id)
        self._set_user(manager)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.booking.booking_crud.get_all', new=get_all):
            response = await self.client.get(
                '/api/v1/booking',
                params={'show_active': 'false'},
            )

        self.assertEqual(response.status_code, 200)
        get_all.assert_awaited_once_with(
            session=self.session,
            show_active=False,
            cafe_id=own_cafe_id,
            user_id=None,
        )

    async def test_get_booking_checks_access_before_returning_it(self) -> None:
        """GET отдельной брони выполняет поиск и проверку прав."""
        booking = _make_booking()
        self.booking_service.get_booking_or_raise.return_value = booking

        response = await self.client.get(f'/api/v1/booking/{booking.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(booking.id))
        self.booking_service.get_booking_or_raise.assert_awaited_once_with(
            booking_id=booking.id,
        )
        self.booking_service.check_user_permission.assert_awaited_once_with(
            booking=booking,
            user=self.current_user,
        )

    async def test_regular_user_cannot_get_another_users_booking(self) -> None:
        """Чужая бронь недоступна обычному пользователю."""
        user = _make_user(UserRole.USER)
        booking = _make_booking(user_id=uuid.uuid4())
        self._set_user(user)
        self.booking_service.get_booking_or_raise.return_value = booking
        self.booking_service.check_user_permission.side_effect = APIError(
            status_code=403,
            message='Доступ запрещен.',
        )

        response = await self.client.get(f'/api/v1/booking/{booking.id}')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'code': 403, 'message': 'Доступ запрещен.'})

    async def test_create_delegates_to_service_and_enqueues_notification(self) -> None:
        """POST делегирует создание сервису и ставит уведомление в очередь."""
        booking = _make_booking(
            user_id=self.current_user.id,
            reminder_minutes_before=45,
        )
        payload = _booking_payload(booking)
        notification_id = uuid.uuid4()
        self.booking_service.create_booking_with_notifications.return_value = (
            booking,
            notification_id,
        )
        enqueue = Mock()

        with patch('api.endpoints.booking.send_booking_notification.delay', new=enqueue):
            response = await self.client.post('/api/v1/booking', json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], str(booking.id))
        self.booking_service.create_booking_with_notifications.assert_awaited_once()
        current_user, new_booking = self.booking_service.create_booking_with_notifications.await_args.args
        self.assertIs(current_user, self.current_user)
        self.assertEqual(new_booking.cafe_id, booking.cafe_id)
        self.assertEqual(new_booking.reminder_minutes_before, 45)
        enqueue.assert_called_once_with(str(notification_id))

    async def test_create_rejects_past_booking_date_before_business_checks(self) -> None:
        """Дата в прошлом отклоняется схемой до обращения к сервисам."""
        booking = _make_booking(booking_date=date.today() - timedelta(days=1))
        response = await self.client.post('/api/v1/booking', json=_booking_payload(booking))

        self.assertEqual(response.status_code, 422)
        self.assertIn('Дата бронирования не может быть меньше текущей даты', response.json()['message'])
        self.booking_service.create_booking_with_notifications.assert_not_awaited()

    async def test_create_rejects_non_positive_reminder_interval(self) -> None:
        """Интервал напоминания должен быть положительным или null."""
        booking = _make_booking()
        payload = _booking_payload(booking)
        payload['reminder_minutes_before'] = 0

        response = await self.client.post('/api/v1/booking', json=payload)

        self.assertEqual(response.status_code, 422)
        self.booking_service.create_booking_with_notifications.assert_not_awaited()

    async def test_patch_delegates_to_service_and_enqueues_notification(self) -> None:
        """PATCH делегирует обновление сервису и ставит уведомление в очередь."""
        booking = _make_booking()
        updated_booking = _make_booking(
            booking_id=booking.id,
            user_id=booking.user_id,
            cafe_id=booking.cafe_id,
            note='Тихое место',
        )
        notification_id = uuid.uuid4()
        self.booking_service.update_booking_with_notifications.return_value = (
            updated_booking,
            notification_id,
        )
        enqueue = Mock()

        with patch('api.endpoints.booking.send_booking_notification.delay', new=enqueue):
            response = await self.client.patch(
                f'/api/v1/booking/{booking.id}',
                json={'note': 'Тихое место'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['note'], 'Тихое место')
        self.booking_service.update_booking_with_notifications.assert_awaited_once()
        call = self.booking_service.update_booking_with_notifications.await_args.kwargs
        self.assertIs(call['current_user'], self.current_user)
        self.assertEqual(call['booking_id'], booking.id)
        self.assertEqual(call['update_data'].note, 'Тихое место')
        enqueue.assert_called_once_with(str(notification_id))

    async def test_patch_passes_tables_guests_and_date_to_service(self) -> None:
        """PATCH передаёт сервису новые столы, слоты, дату и число гостей."""
        booking = _make_booking()
        table_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        booking_date = date.today() + timedelta(days=2)
        notification_id = uuid.uuid4()
        self.booking_service.update_booking_with_notifications.return_value = (
            booking,
            notification_id,
        )

        with patch('api.endpoints.booking.send_booking_notification.delay'):
            response = await self.client.patch(
                f'/api/v1/booking/{booking.id}',
                json={
                    'tables_slots': [
                        {'table_id': str(table_id), 'slot_id': str(slot_id)},
                    ],
                    'booking_date': booking_date.isoformat(),
                    'guest_number': 3,
                },
            )

        self.assertEqual(response.status_code, 200)
        update_data = self.booking_service.update_booking_with_notifications.await_args.kwargs['update_data']
        self.assertEqual(update_data.booking_date, booking_date)
        self.assertEqual(update_data.guest_number, 3)
        self.assertEqual(update_data.tables_slots[0].table_id, table_id)
        self.assertEqual(update_data.tables_slots[0].slot_id, slot_id)

    async def test_user_cannot_deactivate_booking(self) -> None:
        """Обычный пользователь не может менять is_active."""
        user = _make_user(UserRole.USER)
        booking = _make_booking(user_id=user.id)
        self._set_user(user)
        self.booking_service.update_booking_with_notifications.side_effect = APIError(
            status_code=400,
            message='Пользовтель не может реадктировать поле is_active.',
        )

        response = await self.client.patch(
            f'/api/v1/booking/{booking.id}',
            json={'is_active': False},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                'code': 400,
                'message': 'Пользовтель не может реадктировать поле is_active.',
            },
        )
        self.booking_service.update_booking_with_notifications.assert_awaited_once()

    async def test_active_booking_cannot_be_updated(self) -> None:
        """Статус ACTIVE блокирует изменение бронирования для любой роли."""
        booking = _make_booking(status=StatusBooking.ACTIVE)
        self.booking_service.update_booking_with_notifications.side_effect = APIError(
            status_code=400,
            message='Статус бронирования не допускает внесение изменений.',
        )

        response = await self.client.patch(
            f'/api/v1/booking/{booking.id}',
            json={'note': 'Новое примечание'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                'code': 400,
                'message': 'Статус бронирования не допускает внесение изменений.',
            },
        )
        self.booking_service.update_booking_with_notifications.assert_awaited_once()


class BookingRulesTests(IsolatedAsyncioTestCase):
    """Проверяет правила доступа и изменения бронирований без HTTP слоя."""

    def setUp(self) -> None:
        """Создаёт сервис с изолированными зависимостями."""
        self.service = BookingService(
            session=AsyncMock(spec=AsyncSession),
            notification_service=AsyncMock(),
            booking_crud=AsyncMock(),
        )

    def test_split_tables_slots_keeps_pairs_and_collects_ids(self) -> None:
        """Пары стол слот не теряются при подготовке сервисных проверок."""
        first = BookingTableSlot(table_id=uuid.uuid4(), slot_id=uuid.uuid4())
        second = BookingTableSlot(table_id=uuid.uuid4(), slot_id=uuid.uuid4())

        pairs, table_ids, slot_ids = self.service.split_tables_slots([first, second])

        self.assertEqual(pairs, [(first.table_id, first.slot_id), (second.table_id, second.slot_id)])
        self.assertEqual(table_ids, [first.table_id, second.table_id])
        self.assertEqual(slot_ids, [first.slot_id, second.slot_id])

    async def test_create_runs_business_checks_and_persists_notifications(self) -> None:
        """Сервис проверяет новую бронь и сохраняет её вместе с уведомлениями."""
        user = _make_user(UserRole.USER)
        booking = _make_booking(user_id=user.id)
        new_booking = BookingCreate.model_validate(_booking_payload(booking))
        table_slot = new_booking.tables_slots[0]
        notification_id = uuid.uuid4()

        self.service.check_cafe_has_tables_slots = AsyncMock()
        self.service.check_double_booking_exsist = AsyncMock()
        self.service.check_user_have_same_slot = AsyncMock()
        self.service.check_number_geusts_not_more_seat_number = AsyncMock()
        self.service.crud.create.return_value = booking
        self.service.notification_service.create_booking_notifications.return_value = (
            SimpleNamespace(id=notification_id),
            SimpleNamespace(),
        )

        with patch('services.booking.get_cafe_or_404', new=AsyncMock()) as get_cafe:
            result, result_notification_id = await self.service.create_booking_with_notifications(
                user,
                new_booking,
            )

        self.assertIs(result, booking)
        self.assertEqual(result_notification_id, notification_id)
        get_cafe.assert_awaited_once_with(
            cafe_id=booking.cafe_id,
            session=self.service.session,
        )
        self.service.check_cafe_has_tables_slots.assert_awaited_once_with(
            cafe_id=booking.cafe_id,
            table_ids=[table_slot.table_id],
            slot_ids=[table_slot.slot_id],
        )
        self.service.check_double_booking_exsist.assert_awaited_once_with(
            cafe_id=booking.cafe_id,
            booking_date=booking.booking_date,
            table_slot_ids=[(table_slot.table_id, table_slot.slot_id)],
        )
        self.service.check_user_have_same_slot.assert_awaited_once_with(
            booking_date=booking.booking_date,
            user_id=user.id,
            slot_ids=[table_slot.slot_id],
        )
        self.service.check_number_geusts_not_more_seat_number.assert_awaited_once_with(
            guest_number=booking.guest_number,
            table_ids=[table_slot.table_id],
        )
        self.service.crud.create.assert_awaited_once_with(
            obj_in=new_booking,
            session=self.service.session,
            current_user=user,
        )
        self.service.notification_service.create_booking_notifications.assert_awaited_once_with(
            booking,
        )
        self.service.session.commit.assert_awaited_once_with()
        self.service.session.refresh.assert_awaited_once_with(booking)

    async def test_update_revalidates_tables_guests_and_persists_notifications(self) -> None:
        """Сервис повторно проверяет изменённые столы, слоты и число гостей."""
        user = _make_user(UserRole.ADMIN)
        booking = _make_booking()
        table_slot = BookingTableSlot(table_id=uuid.uuid4(), slot_id=uuid.uuid4())
        booking_date = date.today() + timedelta(days=2)
        update_data = BookingUpdate(
            tables_slots=[table_slot],
            booking_date=booking_date,
            guest_number=3,
        )
        updated_booking = _make_booking(
            booking_id=booking.id,
            user_id=booking.user_id,
            cafe_id=booking.cafe_id,
            booking_date=booking_date,
            guest_number=3,
        )
        notification_id = uuid.uuid4()

        self.service.get_booking_or_raise = AsyncMock(return_value=booking)
        self.service.check_user_permission = AsyncMock()
        self.service.check_booking_status = Mock()
        self.service.check_only_is_active_changes = Mock()
        self.service.check_cafe_has_tables_slots = AsyncMock()
        self.service.check_double_booking_exsist = AsyncMock()
        self.service.check_user_have_same_slot = AsyncMock()
        self.service.check_number_geusts_not_more_seat_number = AsyncMock()
        self.service.check_role_user_cant_not_changed_is_active = Mock()
        self.service.crud.update.return_value = updated_booking
        self.service.notification_service.update_booking_notifications.return_value = (
            SimpleNamespace(id=notification_id),
            SimpleNamespace(),
        )

        result, result_notification_id = await self.service.update_booking_with_notifications(
            current_user=user,
            booking_id=booking.id,
            update_data=update_data,
        )

        self.assertIs(result, updated_booking)
        self.assertEqual(result_notification_id, notification_id)
        self.service.get_booking_or_raise.assert_awaited_once_with(booking_id=booking.id)
        self.service.check_user_permission.assert_awaited_once_with(
            booking=booking,
            user=user,
        )
        self.service.check_cafe_has_tables_slots.assert_awaited_once_with(
            cafe_id=booking.cafe_id,
            table_ids=[table_slot.table_id],
            slot_ids=[table_slot.slot_id],
        )
        self.service.check_double_booking_exsist.assert_awaited_once_with(
            cafe_id=booking.cafe_id,
            booking_date=booking_date,
            table_slot_ids=[(table_slot.table_id, table_slot.slot_id)],
            booking_id=booking.id,
        )
        self.service.check_user_have_same_slot.assert_awaited_once_with(
            booking_date=booking_date,
            user_id=booking.user_id,
            slot_ids=[table_slot.slot_id],
            booking_id=booking.id,
        )
        self.service.check_number_geusts_not_more_seat_number.assert_awaited_once_with(
            guest_number=3,
            table_ids=[table_slot.table_id],
        )
        self.service.crud.update.assert_awaited_once_with(
            session=self.service.session,
            db_booking=booking,
            obj_in=update_data,
        )
        self.service.notification_service.update_booking_notifications.assert_awaited_once_with(
            updated_booking,
        )
        self.service.session.commit.assert_awaited_once_with()
        self.service.session.refresh.assert_awaited_once_with(updated_booking)

    async def test_manager_can_access_booking_of_assigned_cafe(self) -> None:
        """Менеджеру доступна бронь другого пользователя в своём кафе."""
        cafe_id = uuid.uuid4()
        manager = _make_user(UserRole.MANAGER, cafe_id=cafe_id)
        booking = _make_booking(user_id=uuid.uuid4(), cafe_id=cafe_id)

        await self.service.check_user_permission(booking, manager)

    async def test_manager_cannot_access_booking_of_another_cafe(self) -> None:
        """Менеджеру запрещена бронь чужого кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=uuid.uuid4())
        booking = _make_booking(user_id=uuid.uuid4(), cafe_id=uuid.uuid4())

        with self.assertRaises(APIError) as raised:
            await self.service.check_user_permission(booking, manager)

        self.assertEqual(raised.exception.status_code, 403)

    def test_deactivation_cannot_be_combined_with_other_changes(self) -> None:
        """is_active=false принимается только отдельным изменением."""
        update = BookingUpdate(is_active=False, note='Одновременно')

        with self.assertRaises(APIError) as raised:
            self.service.check_only_is_active_changes(update)

        self.assertEqual(raised.exception.status_code, 400)

    def test_completed_booking_cannot_be_changed(self) -> None:
        """Статус COMPLETED запрещает любые последующие изменения."""
        booking = _make_booking(status=StatusBooking.COMPLETED)

        with self.assertRaises(APIError) as raised:
            self.service.check_booking_status(booking)

        self.assertEqual(raised.exception.status_code, 400)

    def test_regular_user_cannot_change_activity_flag(self) -> None:
        """Проверка роли запрещает USER менять флаг активности."""
        user = _make_user(UserRole.USER)
        update = BookingUpdate(is_active=True)

        with self.assertRaises(APIError) as raised:
            self.service.check_role_user_cant_not_changed_is_active(update, user)

        self.assertEqual(raised.exception.status_code, 400)
