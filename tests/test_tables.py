import os
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Never
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from api.dependencies.cafe import get_cafe_or_404  # noqa: E402
from api.dependencies.logging import get_current_user_with_logging  # noqa: E402
from api.dependencies.tables import get_table_in_cafe  # noqa: E402
from crud.table import table_crud  # noqa: E402
from main import app  # noqa: E402
from models.user import UserRole  # noqa: E402
from schemas.table import TableCreate  # noqa: E402
from services.errors import EntityNotFoundError  # noqa: E402

from core.db import get_session  # noqa: E402
from core.redis import get_redis_session  # noqa: E402


def _make_user(
    role: UserRole,
    cafe_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    """Создаёт пользователя нужной роли для dependency override."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        username=f'{role.value.lower()}-tester',
        role=role,
        cafe_id=cafe_id,
    )


def _make_cafe(
    *,
    cafe_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    """Создаёт объект кафе, совместимый с CafeShortInfo."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=cafe_id or uuid.uuid4(),
        name='Тестовое кафе',
        address='Москва, Тестовая улица, 1',
        phone='+79991234567',
        description='Кафе для тестов столов',
        photo_id=None,
        managers=[],
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _make_table(
    *,
    cafe_id: uuid.UUID,
    table_id: uuid.UUID | None = None,
    seat_number: int = 4,
    is_active: bool = True,
    description: str | None = 'Стол у окна',
) -> SimpleNamespace:
    """Создаёт объект стола, совместимый с TableInfo."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=table_id or uuid.uuid4(),
        cafe_id=cafe_id,
        seat_number=seat_number,
        description=description,
        is_active=is_active,
        created_at=now,
        updated_at=now,
        cafe=_make_cafe(cafe_id=cafe_id),
    )


class TableAPIContractTests(TestCase):
    """Проверяет опубликованный контракт ручек столов."""

    def test_tables_routes_match_specification(self) -> None:
        """Коллекция и объект столов публикуют заявленные методы."""
        paths = app.openapi()['paths']

        self.assertEqual(set(paths['/api/v1/cafes/{cafe_id}/tables']), {'get', 'post'})
        self.assertEqual(
            set(paths['/api/v1/cafes/{cafe_id}/tables/{table_id}']),
            {'get', 'patch'},
        )


class TableAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP-контракт и права доступа ручек столов."""

    async def asyncSetUp(self) -> None:
        """Подменяет внешние зависимости и создаёт ASGI-клиент."""
        app.dependency_overrides.clear()
        self.session = AsyncMock(spec=AsyncSession)
        self.redis = AsyncMock()
        self.cafe_id = uuid.uuid4()

        async def session_override() -> AsyncGenerator[AsyncSession, None]:
            yield self.session

        async def redis_override() -> AsyncGenerator[AsyncMock, None]:
            yield self.redis

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_redis_session] = redis_override
        self._set_user(_make_user(UserRole.ADMIN))
        self._set_cafe(_make_cafe(cafe_id=self.cafe_id))
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        )

    async def asyncTearDown(self) -> None:
        """Закрывает клиент и очищает dependency overrides."""
        await self.client.aclose()
        app.dependency_overrides.clear()

    @staticmethod
    def _set_user(user: SimpleNamespace) -> None:
        """Подменяет текущего пользователя."""

        async def user_override() -> AsyncGenerator[SimpleNamespace, None]:
            yield user

        app.dependency_overrides[get_current_user_with_logging] = user_override

    @staticmethod
    def _set_cafe(cafe: SimpleNamespace) -> None:
        """Подменяет получение кафе."""

        async def cafe_override() -> SimpleNamespace:
            return cafe

        app.dependency_overrides[get_cafe_or_404] = cafe_override

    @staticmethod
    def _set_table(table: SimpleNamespace) -> None:
        """Подменяет получение стола в кафе."""

        async def table_override() -> SimpleNamespace:
            return table

        app.dependency_overrides[get_table_in_cafe] = table_override

    async def test_admin_list_passes_activity_filter_to_crud(self) -> None:
        """Администратор может запросить только неактивные столы."""
        table = _make_table(cafe_id=self.cafe_id, is_active=False)
        get_by_cafe = AsyncMock(return_value=[table])

        with patch('api.endpoints.tables.table_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/tables',
                params={'show_active': 'false'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(table.id))
        self.assertFalse(response.json()[0]['is_active'])
        get_by_cafe.assert_awaited_once_with(
            cafe_id=self.cafe_id,
            session=self.session,
            show_active=False,
        )

    async def test_list_requires_authentication(self) -> None:
        """Запрос без Bearer-токена получает единый ответ 401."""
        app.dependency_overrides.pop(get_current_user_with_logging)
        get_by_cafe = AsyncMock()

        with patch('api.endpoints.tables.table_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(f'/api/v1/cafes/{self.cafe_id}/tables')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                'code': 401,
                'message': 'Не удалось проверить данные авторизации.',
            },
        )
        self.assertEqual(response.headers['www-authenticate'], 'Bearer')
        get_by_cafe.assert_not_awaited()

    async def test_regular_user_always_gets_only_active_tables(self) -> None:
        """Пользователь не может снять серверный фильтр активности."""
        self._set_user(_make_user(UserRole.USER))
        get_by_cafe = AsyncMock(return_value=[])

        with patch('api.endpoints.tables.table_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/tables',
                params={'show_active': 'false'},
            )

        self.assertEqual(response.status_code, 200)
        get_by_cafe.assert_awaited_once_with(
            cafe_id=self.cafe_id,
            session=self.session,
            show_active=True,
        )

    async def test_manager_always_gets_only_active_tables(self) -> None:
        """Менеджер также получает только активные столы."""
        self._set_user(_make_user(UserRole.MANAGER, cafe_id=self.cafe_id))
        get_by_cafe = AsyncMock(return_value=[])

        with patch('api.endpoints.tables.table_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/tables',
                params={'show_active': 'false'},
            )

        self.assertEqual(response.status_code, 200)
        get_by_cafe.assert_awaited_once_with(
            cafe_id=self.cafe_id,
            session=self.session,
            show_active=True,
        )

    async def test_admin_can_create_table(self) -> None:
        """Администратор создаёт стол в кафе и получает 201."""
        table = _make_table(cafe_id=self.cafe_id)
        create = AsyncMock(return_value=table)

        with patch('api.endpoints.tables.table_crud.create_with_cafe', new=create):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/tables',
                json={'seat_number': 4, 'description': 'Стол у окна'},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], str(table.id))
        create.assert_awaited_once()
        cafe_id, request_schema, session = create.await_args.args
        self.assertEqual(cafe_id, self.cafe_id)
        self.assertEqual(request_schema.seat_number, 4)
        self.assertIs(session, self.session)

    async def test_manager_can_create_table_in_own_cafe(self) -> None:
        """Менеджер создаёт стол только в привязанном кафе."""
        self._set_user(_make_user(UserRole.MANAGER, cafe_id=self.cafe_id))
        table = _make_table(cafe_id=self.cafe_id)
        create = AsyncMock(return_value=table)

        with patch('api.endpoints.tables.table_crud.create_with_cafe', new=create):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/tables',
                json={'seat_number': 4},
            )

        self.assertEqual(response.status_code, 201)
        create.assert_awaited_once()

    async def test_manager_cannot_create_table_in_foreign_cafe(self) -> None:
        """Менеджер не создаёт столы в чужом кафе."""
        own_cafe_id = uuid.uuid4()
        self._set_user(_make_user(UserRole.MANAGER, cafe_id=own_cafe_id))
        create = AsyncMock()

        with patch('api.endpoints.tables.table_crud.create_with_cafe', new=create):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/tables',
                json={'seat_number': 4},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Менеджер может управлять только своим кафе'},
        )
        create.assert_not_awaited()

    async def test_regular_user_cannot_create_table(self) -> None:
        """Создание стола запрещено обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        create = AsyncMock()

        with patch('api.endpoints.tables.table_crud.create_with_cafe', new=create):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/tables',
                json={'seat_number': 4},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'code': 403, 'message': 'Доступ запрещён.'})
        create.assert_not_awaited()

    async def test_regular_user_can_get_active_table(self) -> None:
        """Активный стол доступен обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        table = _make_table(cafe_id=self.cafe_id)
        self._set_table(table)

        response = await self.client.get(f'/api/v1/cafes/{self.cafe_id}/tables/{table.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(table.id))

    async def test_inactive_table_is_hidden_from_regular_user(self) -> None:
        """Неактивный стол выглядит для пользователя как отсутствующий."""
        self._set_user(_make_user(UserRole.USER))
        table = _make_table(cafe_id=self.cafe_id, is_active=False)
        self._set_table(table)

        response = await self.client.get(f'/api/v1/cafes/{self.cafe_id}/tables/{table.id}')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'code': 404, 'message': 'Стол не найден'})

    async def test_missing_table_uses_custom_error_response(self) -> None:
        """Неизвестный стол возвращает единый формат ошибки 404."""

        async def missing_table() -> Never:
            raise EntityNotFoundError('Стол не найден в этом кафе')

        app.dependency_overrides[get_table_in_cafe] = missing_table
        response = await self.client.get(
            f'/api/v1/cafes/{self.cafe_id}/tables/{uuid.uuid4()}',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {'code': 404, 'message': 'Стол не найден в этом кафе'},
        )

    async def test_manager_cannot_get_table_in_foreign_cafe(self) -> None:
        """Менеджер не получает стол чужого кафе."""
        self._set_user(_make_user(UserRole.MANAGER, cafe_id=uuid.uuid4()))
        table = _make_table(cafe_id=self.cafe_id)
        self._set_table(table)

        response = await self.client.get(f'/api/v1/cafes/{self.cafe_id}/tables/{table.id}')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Менеджер может управлять только своим кафе'},
        )

    async def test_manager_can_update_table_in_own_cafe(self) -> None:
        """Менеджер обновляет стол своего кафе."""
        self._set_user(_make_user(UserRole.MANAGER, cafe_id=self.cafe_id))
        table = _make_table(cafe_id=self.cafe_id)
        updated = _make_table(
            cafe_id=self.cafe_id,
            table_id=table.id,
            seat_number=6,
        )
        self._set_table(table)
        update = AsyncMock(return_value=updated)

        with patch('api.endpoints.tables.table_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{self.cafe_id}/tables/{table.id}',
                json={'seat_number': 6},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['seat_number'], 6)
        update.assert_awaited_once()
        db_table, request_schema, session, redis = update.await_args.args
        self.assertIs(db_table, table)
        self.assertEqual(request_schema.seat_number, 6)
        self.assertIs(session, self.session)
        self.assertIs(redis, self.redis)

    async def test_regular_user_cannot_update_table(self) -> None:
        """Обновление стола запрещено обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        table = _make_table(cafe_id=self.cafe_id)
        self._set_table(table)
        update = AsyncMock()

        with patch('api.endpoints.tables.table_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{self.cafe_id}/tables/{table.id}',
                json={'seat_number': 6},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'code': 403, 'message': 'Доступ запрещён.'})
        update.assert_not_awaited()

    async def test_manager_cannot_update_table_in_foreign_cafe(self) -> None:
        """Менеджер не обновляет стол чужого кафе."""
        self._set_user(_make_user(UserRole.MANAGER, cafe_id=uuid.uuid4()))
        table = _make_table(cafe_id=self.cafe_id)
        self._set_table(table)
        update = AsyncMock()

        with patch('api.endpoints.tables.table_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{self.cafe_id}/tables/{table.id}',
                json={'seat_number': 6},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Менеджер может управлять только своим кафе'},
        )
        update.assert_not_awaited()

    async def test_update_rejects_non_positive_seat_number(self) -> None:
        """Неположительное количество мест возвращает 422."""
        table = _make_table(cafe_id=self.cafe_id)
        self._set_table(table)
        update = AsyncMock()

        with patch('api.endpoints.tables.table_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{self.cafe_id}/tables/{table.id}',
                json={'seat_number': 0},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 422)
        self.assertIn('seat_number', response.json()['message'])
        update.assert_not_awaited()


class TableCRUDTests(IsolatedAsyncioTestCase):
    """Проверяет CRUD-операции столов."""

    async def test_create_with_cafe_uses_cafe_id_from_url(self) -> None:
        """create_with_cafe привязывает новый стол к кафе из URL."""
        cafe_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)
        obj_in = TableCreate(seat_number=4, description='Стол у окна')
        created = _make_table(cafe_id=cafe_id, seat_number=4)

        with patch.object(table_crud, 'get', new=AsyncMock(return_value=created)):
            result = await table_crud.create_with_cafe(cafe_id, obj_in, session)

        self.assertIs(result, created)
        db_table = session.add.call_args.args[0]
        self.assertEqual(db_table.cafe_id, cafe_id)
        self.assertEqual(db_table.seat_number, 4)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(db_table)

    async def test_get_by_cafe_applies_activity_filter(self) -> None:
        """get_by_cafe добавляет фильтр активности только когда он задан."""
        cafe_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute.return_value = result

        await table_crud.get_by_cafe(cafe_id, session, show_active=True)
        active_query = session.execute.await_args.args[0]
        active_where = str(active_query).split('WHERE', 1)[1]
        self.assertIn('tables.is_active', active_where)

        await table_crud.get_by_cafe(cafe_id, session, show_active=None)
        all_query = session.execute.await_args.args[0]
        all_where = str(all_query).split('WHERE', 1)[1]
        self.assertNotIn('tables.is_active', all_where)

    async def test_get_by_cafe_and_id_checks_cafe_ownership(self) -> None:
        """Стол возвращается только при совпадении ID стола и кафе."""
        cafe_id = uuid.uuid4()
        table_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)
        table = _make_table(cafe_id=cafe_id, table_id=table_id)
        result = MagicMock()
        result.scalar_one_or_none.return_value = table
        session.execute.return_value = result

        found = await table_crud.get_by_cafe_and_id(cafe_id, table_id, session)

        self.assertIs(found, table)
        query = session.execute.await_args.args[0]
        self.assertIn('tables.id', str(query))
        self.assertIn('tables.cafe_id', str(query))


class TableDependencyTests(IsolatedAsyncioTestCase):
    """Проверяет зависимости кафе и вложенного стола."""

    async def test_get_cafe_or_404_raises_if_cafe_not_found(self) -> None:
        """Неизвестное кафе преобразуется в доменную ошибку."""
        session = AsyncMock()

        with patch('api.dependencies.cafe.cafe_crud.get', new=AsyncMock(return_value=None)):
            with self.assertRaises(EntityNotFoundError) as raised:
                await get_cafe_or_404(uuid.uuid4(), session)

        self.assertEqual(str(raised.exception), 'Кафе не найдено')

    async def test_get_cafe_or_404_returns_cafe_if_exists(self) -> None:
        """Существующее кафе возвращается зависимостью."""
        cafe_id = uuid.uuid4()
        session = AsyncMock()
        cafe = Mock(id=cafe_id)

        with patch('api.dependencies.cafe.cafe_crud.get', new=AsyncMock(return_value=cafe)):
            result = await get_cafe_or_404(cafe_id, session)

        self.assertIs(result, cafe)

    async def test_get_table_in_cafe_raises_if_table_not_found(self) -> None:
        """Чужой или отсутствующий стол преобразуется в 404."""
        cafe_id = uuid.uuid4()
        table_id = uuid.uuid4()
        session = AsyncMock()
        get_by_cafe_and_id = AsyncMock(return_value=None)

        with patch(
            'services.table.table_crud.get_by_cafe_and_id',
            new=get_by_cafe_and_id,
        ):
            with self.assertRaises(EntityNotFoundError) as raised:
                await get_table_in_cafe(cafe_id, table_id, session)

        get_by_cafe_and_id.assert_awaited_once_with(cafe_id, table_id, session)
        self.assertEqual(str(raised.exception), 'Стол не найден в этом кафе')

    async def test_get_table_in_cafe_returns_matching_table(self) -> None:
        """Стол своего кафе возвращается зависимостью."""
        cafe_id = uuid.uuid4()
        table_id = uuid.uuid4()
        session = AsyncMock()
        table = Mock(id=table_id, cafe_id=cafe_id)
        get_by_cafe_and_id = AsyncMock(return_value=table)

        with patch(
            'services.table.table_crud.get_by_cafe_and_id',
            new=get_by_cafe_and_id,
        ):
            result = await get_table_in_cafe(cafe_id, table_id, session)

        get_by_cafe_and_id.assert_awaited_once_with(cafe_id, table_id, session)
        self.assertIs(result, table)
