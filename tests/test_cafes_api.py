import os
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Never
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

from api.dependencies.cafe import get_cafe_or_404  # noqa: E402
from api.dependencies.logging import get_current_user_with_logging  # noqa: E402
from main import app  # noqa: E402
from models.user import UserRole  # noqa: E402
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
    name: str = 'Тестовое кафе',
    is_active: bool = True,
) -> SimpleNamespace:
    """Создаёт объект, совместимый с CafeInfo."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=cafe_id or uuid.uuid4(),
        name=name,
        address='Москва, Тестовая улица, 1',
        phone='+79991234567',
        description='Кафе для API тестов',
        photo_id=None,
        managers=[],
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


class CafeAPIContractTests(TestCase):
    """Проверяет опубликованный контракт ручек кафе."""

    def test_cafes_routes_match_specification(self) -> None:
        """Коллекция и объект кафе публикуют только заявленные методы."""
        paths = app.openapi()['paths']

        self.assertEqual(set(paths['/cafes']), {'get', 'post'})
        self.assertEqual(set(paths['/cafes/{cafe_id}']), {'get', 'patch'})


class CafeAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP-контракт и права доступа ручек /cafes."""

    async def asyncSetUp(self) -> None:
        """Подменяет внешние зависимости и создаёт ASGI-клиент."""
        app.dependency_overrides.clear()
        self.session = AsyncMock(spec=AsyncSession)
        self.redis = AsyncMock()

        async def session_override() -> AsyncGenerator[AsyncSession, None]:
            yield self.session

        async def redis_override() -> AsyncGenerator[AsyncMock, None]:
            yield self.redis

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_redis_session] = redis_override
        self._set_user(_make_user(UserRole.ADMIN))
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

        async def user_override() -> AsyncGenerator[SimpleNamespace, None]:
            yield user

        app.dependency_overrides[get_current_user_with_logging] = user_override

    @staticmethod
    def _set_cafe(cafe: SimpleNamespace) -> None:
        """Подменяет получение кафе по идентификатору."""

        async def cafe_override() -> SimpleNamespace:
            return cafe

        app.dependency_overrides[get_cafe_or_404] = cafe_override

    async def test_admin_list_passes_activity_filter_to_crud(self) -> None:
        """Администратор может запросить только неактивные кафе."""
        cafe = _make_cafe(is_active=False)
        get_all = AsyncMock(return_value=[cafe])

        with patch('api.endpoints.cafe.cafe_crud.get_all', new=get_all):
            response = await self.client.get('/cafes', params={'show_active': 'false'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(cafe.id))
        self.assertFalse(response.json()[0]['is_active'])
        get_all.assert_awaited_once_with(
            session=self.session,
            show_active=False,
        )

    async def test_list_requires_authentication(self) -> None:
        """Запрос без Bearer-токена получает единый ответ 401."""
        app.dependency_overrides.pop(get_current_user_with_logging)
        get_all = AsyncMock()

        with patch('api.endpoints.cafe.cafe_crud.get_all', new=get_all):
            response = await self.client.get('/cafes')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                'code': 401,
                'message': 'Не удалось проверить данные авторизации.',
            },
        )
        self.assertEqual(response.headers['www-authenticate'], 'Bearer')
        get_all.assert_not_awaited()

    async def test_regular_user_always_gets_only_active_cafes(self) -> None:
        """Пользователь не может снять серверный фильтр активности."""
        self._set_user(_make_user(UserRole.USER))
        cafe = _make_cafe()
        get_all = AsyncMock(return_value=[cafe])

        with patch('api.endpoints.cafe.cafe_crud.get_all', new=get_all):
            response = await self.client.get('/cafes', params={'show_active': 'false'})

        self.assertEqual(response.status_code, 200)
        get_all.assert_awaited_once_with(
            session=self.session,
            show_active=True,
        )

    async def test_manager_gets_only_assigned_cafe(self) -> None:
        """Список менеджера формируется сервисом его собственного кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=uuid.uuid4())
        cafe = _make_cafe(cafe_id=manager.cafe_id)
        self._set_user(manager)
        get_manager_cafes = AsyncMock(return_value=[cafe])

        with patch(
            'api.endpoints.cafe.get_manager_cafes',
            new=get_manager_cafes,
        ):
            response = await self.client.get('/cafes')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(manager.cafe_id))
        get_manager_cafes.assert_awaited_once()
        self.assertIs(get_manager_cafes.await_args.args[0], manager)
        self.assertIs(get_manager_cafes.await_args.args[1], self.session)

    async def test_admin_can_create_cafe(self) -> None:
        """POST /cafes возвращает 201 и передаёт данные в CRUD."""
        cafe = _make_cafe()
        manager_id = uuid.uuid4()
        create = AsyncMock(return_value=cafe)
        payload = {
            'name': cafe.name,
            'address': cafe.address,
            'phone': cafe.phone,
            'description': cafe.description,
            'managers_id': [str(manager_id)],
        }

        with patch('api.endpoints.cafe.cafe_crud.create', new=create):
            response = await self.client.post('/cafes', json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], cafe.name)
        create.assert_awaited_once()
        request_schema, session, redis = create.await_args.args
        self.assertEqual(request_schema.name, cafe.name)
        self.assertEqual(request_schema.managers_id, [manager_id])
        self.assertIs(session, self.session)
        self.assertIs(redis, self.redis)

    async def test_regular_user_cannot_create_cafe(self) -> None:
        """Создание кафе запрещено обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        create = AsyncMock()

        with patch('api.endpoints.cafe.cafe_crud.create', new=create):
            response = await self.client.post(
                '/cafes',
                json={
                    'name': 'Новое кафе',
                    'address': 'Москва, Новая улица, 1',
                    'phone': '+79991234568',
                    'managers_id': [str(uuid.uuid4())],
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'code': 403, 'message': 'Доступ запрещён.'})
        create.assert_not_awaited()

    async def test_user_can_get_active_cafe_by_id(self) -> None:
        """Активное кафе доступно обычному пользователю."""
        cafe = _make_cafe()
        self._set_user(_make_user(UserRole.USER))
        self._set_cafe(cafe)

        response = await self.client.get(f'/cafes/{cafe.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(cafe.id))

    async def test_inactive_cafe_is_hidden_from_regular_user(self) -> None:
        """Неактивное кафе выглядит для пользователя как отсутствующее."""
        cafe = _make_cafe(is_active=False)
        self._set_user(_make_user(UserRole.USER))
        self._set_cafe(cafe)

        response = await self.client.get(f'/cafes/{cafe.id}')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'code': 404, 'message': 'Кафе не найдено'})

    async def test_missing_cafe_uses_custom_error_response(self) -> None:
        """Неизвестный UUID возвращает единый формат ошибки 404."""

        async def missing_cafe() -> Never:
            raise EntityNotFoundError('Кафе не найдено')

        app.dependency_overrides[get_cafe_or_404] = missing_cafe

        response = await self.client.get(f'/cafes/{uuid.uuid4()}')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'code': 404, 'message': 'Кафе не найдено'})

    async def test_manager_cannot_get_foreign_cafe(self) -> None:
        """Менеджер получает 403 при обращении к чужому кафе."""
        own_cafe_id = uuid.uuid4()
        foreign_cafe = _make_cafe()
        self._set_user(_make_user(UserRole.MANAGER, cafe_id=own_cafe_id))
        self._set_cafe(foreign_cafe)

        response = await self.client.get(f'/cafes/{foreign_cafe.id}')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Менеджер может управлять только своим кафе'},
        )

    async def test_manager_can_update_own_cafe(self) -> None:
        """Менеджер может изменить привязанное к нему кафе."""
        cafe_id = uuid.uuid4()
        cafe = _make_cafe(cafe_id=cafe_id)
        updated_cafe = _make_cafe(cafe_id=cafe_id, name='Обновлённое кафе')
        manager = _make_user(UserRole.MANAGER, cafe_id=cafe_id)
        self._set_user(manager)
        self._set_cafe(cafe)
        update = AsyncMock(return_value=updated_cafe)

        with patch('api.endpoints.cafe.cafe_crud.update', new=update):
            response = await self.client.patch(
                f'/cafes/{cafe_id}',
                json={'name': updated_cafe.name},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], updated_cafe.name)
        update.assert_awaited_once()
        db_cafe, request_schema, session, redis = update.await_args.args
        self.assertIs(db_cafe, cafe)
        self.assertEqual(request_schema.name, updated_cafe.name)
        self.assertIs(session, self.session)
        self.assertIs(redis, self.redis)

    async def test_regular_user_cannot_update_cafe(self) -> None:
        """PATCH /cafes/{id} запрещён обычному пользователю."""
        cafe = _make_cafe()
        self._set_user(_make_user(UserRole.USER))
        self._set_cafe(cafe)
        update = AsyncMock()

        with patch('api.endpoints.cafe.cafe_crud.update', new=update):
            response = await self.client.patch(
                f'/cafes/{cafe.id}',
                json={'name': 'Недоступное обновление'},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'code': 403, 'message': 'Доступ запрещён.'})
        update.assert_not_awaited()

    async def test_update_rejects_explicit_null_for_required_field(self) -> None:
        """Явный null в обязательном поле возвращает форматированную 422."""
        cafe = _make_cafe()
        self._set_cafe(cafe)
        update = AsyncMock()

        with patch('api.endpoints.cafe.cafe_crud.update', new=update):
            response = await self.client.patch(
                f'/cafes/{cafe.id}',
                json={'name': None},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 422)
        self.assertIn('name', response.json()['message'])
        update.assert_not_awaited()
