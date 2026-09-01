import os
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
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

from api.dependencies.logging import (  # noqa: E402
    get_current_user_with_logging,
    get_me_user_with_logging,
)
from crud.user import UserAlreadyExistsError, UserNotFoundError  # noqa: E402
from main import app  # noqa: E402
from models.user import UserRole  # noqa: E402

from core.db import get_session  # noqa: E402
from core.redis import get_redis_session  # noqa: E402


def _make_user(
    *,
    role: UserRole = UserRole.USER,
    user_id: uuid.UUID | None = None,
    username: str = 'tester',
    email: str | None = 'tester@example.com',
    phone: str | None = None,
    is_active: bool = True,
    cafe_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    """Создаёт объект, совместимый с публичной схемой пользователя."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=user_id or uuid.uuid4(),
        username=username,
        email=email,
        phone=phone,
        tg_id=None,
        role=role,
        is_active=is_active,
        cafe_id=cafe_id,
        created_at=now,
        updated_at=now,
    )


class UserAPIContractTests(TestCase):
    """Проверяет опубликованный контракт группы /users."""

    def test_user_routes_match_specification(self) -> None:
        """Коллекция, текущий пользователь и объект имеют нужные методы."""
        paths = app.openapi()['paths']

        self.assertEqual(set(paths['/api/v1/users']), {'get', 'post'})
        self.assertEqual(set(paths['/api/v1/users/me']), {'get', 'patch'})
        self.assertEqual(set(paths['/api/v1/users/{user_id}']), {'get', 'patch'})


class UserAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP-контракт, валидацию и права ручек /users."""

    async def asyncSetUp(self) -> None:
        """Подменяет внешние зависимости и создаёт ASGI-клиент."""
        app.dependency_overrides.clear()
        self.session = AsyncMock(spec=AsyncSession)
        self.admin = _make_user(role=UserRole.ADMIN, username='admin')
        self._set_actor(self.admin)

        async def session_override() -> AsyncGenerator[AsyncSession, None]:
            yield self.session

        async def redis_override() -> AsyncGenerator[AsyncMock, None]:
            yield AsyncMock()

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_redis_session] = redis_override
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        )

    async def asyncTearDown(self) -> None:
        """Закрывает клиент и очищает глобальные dependency overrides."""
        await self.client.aclose()
        app.dependency_overrides.clear()

    @staticmethod
    def _set_actor(user: SimpleNamespace) -> None:
        """Подменяет текущего пользователя для staff и me зависимостей."""

        async def user_override() -> AsyncGenerator[SimpleNamespace, None]:
            yield user

        app.dependency_overrides[get_current_user_with_logging] = user_override
        app.dependency_overrides[get_me_user_with_logging] = user_override

    async def test_registration_creates_validated_user(self) -> None:
        """Регистрация валидирует данные и возвращает 201 без пароля."""
        created_user = _make_user(
            username='New User',
            email='new@example.com',
        )
        create = AsyncMock(return_value=created_user)

        with patch('api.endpoints.user.user_crud.create', new=create):
            response = await self.client.post(
                '/api/v1/users',
                json={
                    'username': '  New User  ',
                    'email': 'NEW@EXAMPLE.COM',
                    'password': 'strong-password',
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['username'], 'New User')
        self.assertNotIn('password', response.json())
        self.assertNotIn('hashed_password', response.json())
        create.assert_awaited_once()
        user_create, session = create.await_args.args
        self.assertEqual(user_create.username, 'New User')
        self.assertEqual(str(user_create.email), 'NEW@example.com')
        self.assertEqual(
            user_create.password,
            'strong-password',
        )
        self.assertIs(session, self.session)

    async def test_registration_rejects_privilege_fields(self) -> None:
        """Клиент не может назначить роль или активность при регистрации."""
        create = AsyncMock()

        with patch('api.endpoints.user.user_crud.create', new=create):
            response = await self.client.post(
                '/api/v1/users',
                json={
                    'username': 'new-user',
                    'email': 'new@example.com',
                    'password': 'strong-password',
                    'role': 'ADMIN',
                    'is_active': False,
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 422)
        create.assert_not_awaited()

    async def test_registration_requires_email_or_phone(self) -> None:
        """Регистрация без контактных данных завершается валидацией 422."""
        create = AsyncMock()

        with patch('api.endpoints.user.user_crud.create', new=create):
            response = await self.client.post(
                '/api/v1/users',
                json={
                    'username': 'new-user',
                    'password': 'strong-password',
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 422)
        create.assert_not_awaited()

    async def test_registration_conflict_uses_custom_error(self) -> None:
        """Дубликат публичных идентификаторов возвращает единый ответ 400."""
        create = AsyncMock(side_effect=UserAlreadyExistsError)

        with patch('api.endpoints.user.user_crud.create', new=create):
            response = await self.client.post(
                '/api/v1/users',
                json={
                    'username': 'existing-user',
                    'email': 'existing@example.com',
                    'password': 'strong-password',
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                'code': 400,
                'message': 'Пользователь с такими данными уже существует.',
            },
        )

    async def test_staff_can_get_all_users(self) -> None:
        """Администратор получает список пользователей через CRUD."""
        user = _make_user()
        get_all = AsyncMock(return_value=[user])

        with patch('api.endpoints.user.user_crud.get_all', new=get_all):
            response = await self.client.get('/api/v1/users')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(user.id))
        get_all.assert_awaited_once_with(self.session)

    async def test_regular_user_cannot_get_all_users(self) -> None:
        """Обычный пользователь не имеет доступа к списку пользователей."""
        self._set_actor(_make_user())
        get_all = AsyncMock()

        with patch('api.endpoints.user.user_crud.get_all', new=get_all):
            response = await self.client.get('/api/v1/users')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Доступ запрещён.'},
        )
        get_all.assert_not_awaited()

    async def test_current_user_can_get_own_profile(self) -> None:
        """Авторизованный пользователь получает собственный профиль."""
        user = _make_user(phone='+79991234567')
        self._set_actor(user)

        response = await self.client.get('/api/v1/users/me')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(user.id))
        self.assertNotIn('hashed_password', response.json())

    async def test_get_me_without_token_returns_403(self) -> None:
        """Специальный контракт /users/me возвращает 403 без токена."""
        app.dependency_overrides.pop(get_me_user_with_logging)

        response = await self.client.get('/api/v1/users/me')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Доступ запрещён.'},
        )

    async def test_update_me_ignores_role_and_activity(self) -> None:
        """Пользователь не может изменить себе роль или активность."""
        user = _make_user()
        self._set_actor(user)
        update = AsyncMock(return_value=user)

        with patch('api.endpoints.user.user_crud.update', new=update):
            response = await self.client.patch(
                '/api/v1/users/me',
                json={
                    'username': 'updated-user',
                    'role': 'ADMIN',
                    'is_active': False,
                },
            )

        self.assertEqual(response.status_code, 200)
        update.assert_awaited_once()
        target, update_data, session = update.await_args.args
        self.assertIs(target, user)
        self.assertEqual(update_data, {'username': 'updated-user'})
        self.assertIs(session, self.session)

    async def test_update_me_cannot_remove_last_contact(self) -> None:
        """Пользователь не может удалить единственный контакт для входа."""
        user = _make_user(email='tester@example.com', phone=None)
        self._set_actor(user)
        update = AsyncMock()

        with patch('api.endpoints.user.user_crud.update', new=update):
            response = await self.client.patch(
                '/api/v1/users/me',
                json={'email': None},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {'code': 400, 'message': 'Необходимо указать email или телефон.'},
        )
        update.assert_not_awaited()

    async def test_staff_can_get_user_by_id(self) -> None:
        """Сотрудник получает выбранного пользователя через CRUD."""
        target = _make_user()
        get_or_raise = AsyncMock(return_value=target)

        with patch(
            'api.endpoints.user.user_crud.get_or_raise',
            new=get_or_raise,
        ):
            response = await self.client.get(f'/api/v1/users/{target.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(target.id))
        get_or_raise.assert_awaited_once_with(target.id, self.session)

    async def test_missing_user_uses_custom_error(self) -> None:
        """Неизвестный UUID возвращает единый ответ 404."""
        get_or_raise = AsyncMock(side_effect=UserNotFoundError)
        user_id = uuid.uuid4()

        with patch(
            'api.endpoints.user.user_crud.get_or_raise',
            new=get_or_raise,
        ):
            response = await self.client.get(f'/api/v1/users/{user_id}')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {'code': 404, 'message': 'Пользователь не найден.'},
        )

    async def test_manager_cannot_update_admin(self) -> None:
        """Менеджер не может менять данные администратора."""
        manager = _make_user(role=UserRole.MANAGER, username='manager')
        target = _make_user(role=UserRole.ADMIN, username='target-admin')
        self._set_actor(manager)
        update = AsyncMock()

        with (
            patch(
                'api.endpoints.user.user_crud.get_or_raise',
                new=AsyncMock(return_value=target),
            ),
            patch('api.endpoints.user.user_crud.update', new=update),
        ):
            response = await self.client.patch(
                f'/api/v1/users/{target.id}',
                json={'username': 'changed-admin'},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {
                'code': 403,
                'message': (
                    'Менеджер не может изменять администратора '
                    'или назначать эту роль.'
                ),
            },
        )
        update.assert_not_awaited()

    async def test_admin_role_change_clears_cafe_assignment(self) -> None:
        """При снятии роли менеджера удаляется его привязка к кафе."""
        target = _make_user(
            role=UserRole.MANAGER,
            username='manager',
            cafe_id=uuid.uuid4(),
        )
        update = AsyncMock(return_value=target)

        with (
            patch(
                'api.endpoints.user.user_crud.get_or_raise',
                new=AsyncMock(return_value=target),
            ),
            patch('api.endpoints.user.user_crud.update', new=update),
        ):
            response = await self.client.patch(
                f'/api/v1/users/{target.id}',
                json={'role': 'USER'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(target.cafe_id)
        update.assert_awaited_once()
        _, update_data, session = update.await_args.args
        self.assertEqual(update_data, {'role': UserRole.USER})
        self.assertIs(session, self.session)

    async def test_invalid_user_id_is_rejected_before_crud(self) -> None:
        """Некорректный UUID возвращает 422 без обращения к CRUD."""
        get_or_raise = AsyncMock()

        with patch(
            'api.endpoints.user.user_crud.get_or_raise',
            new=get_or_raise,
        ):
            response = await self.client.get('/api/v1/users/not-a-uuid')

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 422)
        get_or_raise.assert_not_awaited()
