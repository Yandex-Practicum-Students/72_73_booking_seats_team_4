import os
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from api.dependencies.logging import get_current_user_with_logging  # noqa: E402
from api.errors import APIError  # noqa: E402
from main import app  # noqa: E402
from models.booking import StatusBooking  # noqa: E402
from models.user import UserRole  # noqa: E402
from schemas.booking import BookingTableSlot, BookingUpdate  # noqa: E402
from services.booking import (  # noqa: E402
    check_booking_status,
    check_only_is_active_changes,
    check_role_user_cant_not_changed_is_active,
    check_user_permission,
    split_tables_slots,
)

from core.db import get_session  # noqa: E402


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

        self.assertEqual(set(paths['/booking']), {'get', 'post'})
        self.assertEqual(set(paths['/booking/{booking_id}']), {'get', 'patch'})


class BookingAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP контракт и бизнес ограничения ручек /booking."""

    async def asyncSetUp(self) -> None:
        """Подменяет внешние зависимости и создаёт ASGI клиент."""
        app.dependency_overrides.clear()
        self.session = AsyncMock(spec=AsyncSession)

        async def session_override() -> AsyncGenerator[AsyncSession, None]:
            yield self.session

        app.dependency_overrides[get_session] = session_override
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
            response = await self.client.get('/booking')

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
                '/booking',
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
                '/booking',
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
                '/booking',
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
                '/booking',
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
        get_booking = AsyncMock(return_value=booking)
        check_permission = AsyncMock()

        with (
            patch('api.endpoints.booking.get_booking_or_raise', new=get_booking),
            patch('api.endpoints.booking.check_user_permission', new=check_permission),
        ):
            response = await self.client.get(f'/booking/{booking.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(booking.id))
        get_booking.assert_awaited_once_with(
            booking_id=booking.id,
            session=self.session,
        )
        check_permission.assert_awaited_once_with(
            booking=booking,
            user=self.current_user,
        )

    async def test_regular_user_cannot_get_another_users_booking(self) -> None:
        """Чужая бронь недоступна обычному пользователю."""
        user = _make_user(UserRole.USER)
        booking = _make_booking(user_id=uuid.uuid4())
        self._set_user(user)

        with patch(
            'api.endpoints.booking.get_booking_or_raise',
            new=AsyncMock(return_value=booking),
        ):
            response = await self.client.get(f'/booking/{booking.id}')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'code': 403, 'message': 'Доступ запрещен.'})

    async def test_create_runs_all_checks_and_returns_created_booking(self) -> None:
        """POST выполняет проверки в нужном порядке и возвращает 201."""
        booking = _make_booking(user_id=self.current_user.id)
        payload = _booking_payload(booking)
        calls: list[str] = []

        async def record(name: str, result: object = None) -> object:
            calls.append(name)
            return result

        async def record_cafe(**_: object) -> object:
            return await record('cafe')

        async def record_tables_slots(**_: object) -> object:
            return await record('tables_slots')

        async def record_double_booking(**_: object) -> object:
            return await record('double_booking')

        async def record_user_slot(**_: object) -> object:
            return await record('user_slot')

        async def record_seats(**_: object) -> object:
            return await record('seats')

        async def record_create(**_: object) -> object:
            return await record('create', booking)

        get_cafe = AsyncMock(side_effect=record_cafe)
        check_cafe = AsyncMock(side_effect=record_tables_slots)
        check_double = AsyncMock(side_effect=record_double_booking)
        check_user_slot = AsyncMock(side_effect=record_user_slot)
        check_seats = AsyncMock(side_effect=record_seats)
        create = AsyncMock(side_effect=record_create)

        with (
            patch('api.endpoints.booking.get_cafe_or_404', new=get_cafe),
            patch('api.endpoints.booking.check_cafe_has_tables_slots', new=check_cafe),
            patch('api.endpoints.booking.check_double_booking_exsist', new=check_double),
            patch('api.endpoints.booking.check_user_have_same_slot', new=check_user_slot),
            patch(
                'api.endpoints.booking.check_number_geusts_not_more_seat_number',
                new=check_seats,
            ),
            patch('api.endpoints.booking.booking_crud.create', new=create),
        ):
            response = await self.client.post('/booking', json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], str(booking.id))
        self.assertEqual(
            calls,
            ['cafe', 'tables_slots', 'double_booking', 'user_slot', 'seats', 'create'],
        )
        create.assert_awaited_once()
        self.assertEqual(create.await_args.kwargs['obj_in'].cafe_id, booking.cafe_id)
        self.assertIs(create.await_args.kwargs['session'], self.session)
        self.assertIs(create.await_args.kwargs['current_user'], self.current_user)

    async def test_create_rejects_past_booking_date_before_business_checks(self) -> None:
        """Дата в прошлом отклоняется схемой до обращения к сервисам."""
        booking = _make_booking(booking_date=date.today() - timedelta(days=1))
        create = AsyncMock()

        with patch('api.endpoints.booking.booking_crud.create', new=create):
            response = await self.client.post('/booking', json=_booking_payload(booking))

        self.assertEqual(response.status_code, 422)
        self.assertIn('Дата бронирования не может быть меньше текущей даты', response.json()['message'])
        create.assert_not_awaited()

    async def test_patch_without_tables_updates_booking_directly(self) -> None:
        """Простое изменение примечания не запускает проверки столов и слотов."""
        booking = _make_booking()
        updated_booking = _make_booking(
            booking_id=booking.id,
            user_id=booking.user_id,
            cafe_id=booking.cafe_id,
            note='Тихое место',
        )
        get_booking = AsyncMock(return_value=booking)
        update = AsyncMock(return_value=updated_booking)
        check_tables = AsyncMock()
        check_seats = AsyncMock()

        with (
            patch('api.endpoints.booking.get_booking_or_raise', new=get_booking),
            patch('api.endpoints.booking.check_user_permission', new=AsyncMock()),
            patch('api.endpoints.booking.check_cafe_has_tables_slots', new=check_tables),
            patch(
                'api.endpoints.booking.check_number_geusts_not_more_seat_number',
                new=check_seats,
            ),
            patch('api.endpoints.booking.booking_crud.update', new=update),
        ):
            response = await self.client.patch(
                f'/booking/{booking.id}',
                json={'note': 'Тихое место'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['note'], 'Тихое место')
        check_tables.assert_not_awaited()
        check_seats.assert_not_awaited()
        update.assert_awaited_once()
        self.assertIs(update.await_args.kwargs['db_booking'], booking)
        self.assertEqual(update.await_args.kwargs['obj_in'].note, 'Тихое место')

    async def test_patch_tables_and_guests_revalidates_booking(self) -> None:
        """Новые столы, слоты, дата и гости проходят полный набор проверок."""
        booking = _make_booking()
        table_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        booking_date = date.today() + timedelta(days=2)
        update = AsyncMock(return_value=booking)
        check_cafe = AsyncMock()
        check_double = AsyncMock()
        check_user_slot = AsyncMock()
        check_seats = AsyncMock()

        with (
            patch(
                'api.endpoints.booking.get_booking_or_raise',
                new=AsyncMock(return_value=booking),
            ),
            patch('api.endpoints.booking.check_user_permission', new=AsyncMock()),
            patch('api.endpoints.booking.check_cafe_has_tables_slots', new=check_cafe),
            patch('api.endpoints.booking.check_double_booking_exsist', new=check_double),
            patch('api.endpoints.booking.check_user_have_same_slot', new=check_user_slot),
            patch(
                'api.endpoints.booking.check_number_geusts_not_more_seat_number',
                new=check_seats,
            ),
            patch('api.endpoints.booking.booking_crud.update', new=update),
        ):
            response = await self.client.patch(
                f'/booking/{booking.id}',
                json={
                    'tables_slots': [
                        {'table_id': str(table_id), 'slot_id': str(slot_id)},
                    ],
                    'booking_date': booking_date.isoformat(),
                    'guest_number': 3,
                },
            )

        self.assertEqual(response.status_code, 200)
        check_cafe.assert_awaited_once_with(
            session=self.session,
            cafe_id=booking.cafe_id,
            table_ids=[table_id],
            slot_ids=[slot_id],
        )
        check_double.assert_awaited_once_with(
            session=self.session,
            cafe_id=booking.cafe_id,
            booking_date=booking_date,
            table_slot_ids=[(table_id, slot_id)],
            booking_id=booking.id,
        )
        check_user_slot.assert_awaited_once_with(
            session=self.session,
            booking_date=booking_date,
            user_id=booking.user_id,
            slot_ids=[slot_id],
            booking_id=booking.id,
        )
        check_seats.assert_awaited_once_with(
            session=self.session,
            guest_number=3,
            table_ids=[table_id],
        )
        update.assert_awaited_once()

    async def test_user_cannot_deactivate_booking(self) -> None:
        """Обычный пользователь не может менять is_active."""
        user = _make_user(UserRole.USER)
        booking = _make_booking(user_id=user.id)
        self._set_user(user)
        update = AsyncMock()

        with (
            patch(
                'api.endpoints.booking.get_booking_or_raise',
                new=AsyncMock(return_value=booking),
            ),
            patch('api.endpoints.booking.booking_crud.update', new=update),
        ):
            response = await self.client.patch(
                f'/booking/{booking.id}',
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
        update.assert_not_awaited()

    async def test_active_booking_cannot_be_updated(self) -> None:
        """Статус ACTIVE блокирует изменение бронирования для любой роли."""
        booking = _make_booking(status=StatusBooking.ACTIVE)
        update = AsyncMock()

        with (
            patch(
                'api.endpoints.booking.get_booking_or_raise',
                new=AsyncMock(return_value=booking),
            ),
            patch('api.endpoints.booking.check_user_permission', new=AsyncMock()),
            patch('api.endpoints.booking.booking_crud.update', new=update),
        ):
            response = await self.client.patch(
                f'/booking/{booking.id}',
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
        update.assert_not_awaited()


class BookingRulesTests(IsolatedAsyncioTestCase):
    """Проверяет правила доступа и изменения бронирований без HTTP слоя."""

    def test_split_tables_slots_keeps_pairs_and_collects_ids(self) -> None:
        """Пары стол слот не теряются при подготовке сервисных проверок."""
        first = BookingTableSlot(table_id=uuid.uuid4(), slot_id=uuid.uuid4())
        second = BookingTableSlot(table_id=uuid.uuid4(), slot_id=uuid.uuid4())

        pairs, table_ids, slot_ids = split_tables_slots([first, second])

        self.assertEqual(pairs, [(first.table_id, first.slot_id), (second.table_id, second.slot_id)])
        self.assertEqual(table_ids, [first.table_id, second.table_id])
        self.assertEqual(slot_ids, [first.slot_id, second.slot_id])

    async def test_manager_can_access_booking_of_assigned_cafe(self) -> None:
        """Менеджеру доступна бронь другого пользователя в своём кафе."""
        cafe_id = uuid.uuid4()
        manager = _make_user(UserRole.MANAGER, cafe_id=cafe_id)
        booking = _make_booking(user_id=uuid.uuid4(), cafe_id=cafe_id)

        await check_user_permission(booking, manager)

    async def test_manager_cannot_access_booking_of_another_cafe(self) -> None:
        """Менеджеру запрещена бронь чужого кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=uuid.uuid4())
        booking = _make_booking(user_id=uuid.uuid4(), cafe_id=uuid.uuid4())

        with self.assertRaises(APIError) as raised:
            await check_user_permission(booking, manager)

        self.assertEqual(raised.exception.status_code, 403)

    def test_deactivation_cannot_be_combined_with_other_changes(self) -> None:
        """is_active=false принимается только отдельным изменением."""
        update = BookingUpdate(is_active=False, note='Одновременно')

        with self.assertRaises(APIError) as raised:
            check_only_is_active_changes(update)

        self.assertEqual(raised.exception.status_code, 400)

    def test_completed_booking_cannot_be_changed(self) -> None:
        """Статус COMPLETED запрещает любые последующие изменения."""
        booking = _make_booking(status=StatusBooking.COMPLETED)

        with self.assertRaises(APIError) as raised:
            check_booking_status(booking)

        self.assertEqual(raised.exception.status_code, 400)

    def test_regular_user_cannot_change_activity_flag(self) -> None:
        """Проверка роли запрещает USER менять флаг активности."""
        user = _make_user(UserRole.USER)
        update = BookingUpdate(is_active=True)

        with self.assertRaises(APIError) as raised:
            check_role_user_cant_not_changed_is_active(update, user)

        self.assertEqual(raised.exception.status_code, 400)
