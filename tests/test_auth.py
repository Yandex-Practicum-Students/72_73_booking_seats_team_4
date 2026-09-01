import os
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from main import app  # noqa: E402

from core.db import get_session  # noqa: E402
from core.redis import get_redis_session  # noqa: E402
from core.settings import settings  # noqa: E402
from core.user import (  # noqa: E402
    DUMMY_PASSWORD_HASH,
    TOKEN_SESSION_KEY_PREFIX,
    create_access_token,
    decode_access_token,
    get_current_user,
)


def _make_user(*, is_active: bool = True) -> SimpleNamespace:
    """Создаёт минимального пользователя для проверки авторизации."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        hashed_password='stored-password-hash',
        is_active=is_active,
    )


class AuthAPIContractTests(TestCase):
    """Проверяет опубликованный контракт ручек авторизации."""

    def test_auth_routes_match_specification(self) -> None:
        """Авторизация публикует только POST /auth/login."""
        paths = app.openapi()['paths']

        self.assertEqual(set(paths['/api/v1/auth/login']), {'post'})


class AuthAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP-контракт POST /auth/login."""

    async def asyncSetUp(self) -> None:
        """Подменяет сессию базы данных и создаёт ASGI-клиент."""
        app.dependency_overrides.clear()
        self.session = AsyncMock(spec=AsyncSession)
        self.redis = AsyncMock()

        async def session_override() -> AsyncGenerator[AsyncSession, None]:
            yield self.session

        async def redis_override() -> AsyncGenerator[AsyncMock, None]:
            yield self.redis

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

    async def test_active_user_can_login_by_normalized_email(self) -> None:
        """Корректный email и пароль возвращают Bearer JWT пользователя."""
        user = _make_user()
        get_by_login = AsyncMock(return_value=user)

        with (
            patch(
                'api.endpoints.user.user_crud.get_by_login',
                new=get_by_login,
            ),
            patch(
                'api.endpoints.user.verify_password',
                return_value=(True, None),
            ) as verify,
        ):
            response = await self.client.post(
                '/api/v1/auth/login',
                json={
                    'login': '  TESTER@EXAMPLE.COM  ',
                    'password': 'correct-password',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['token_type'], 'bearer')
        self.assertEqual(
            decode_access_token(response.json()['access_token']),
            user.id,
        )
        get_by_login.assert_awaited_once_with(
            'tester@example.com',
            self.session,
        )
        verify.assert_called_once_with(
            'correct-password',
            user.hashed_password,
        )
        self.session.commit.assert_not_awaited()
        redis_call = self.redis.set.await_args
        self.assertTrue(redis_call.args[0].startswith(TOKEN_SESSION_KEY_PREFIX))
        self.assertEqual(redis_call.args[1], str(user.id))
        self.assertEqual(
            redis_call.kwargs['ex'],
            settings.jwt_lifetime_seconds,
        )

    async def test_phone_login_is_normalized(self) -> None:
        """Телефон перед поиском пользователя приводится к формату E.164."""
        user = _make_user()
        get_by_login = AsyncMock(return_value=user)

        with (
            patch(
                'api.endpoints.user.user_crud.get_by_login',
                new=get_by_login,
            ),
            patch(
                'api.endpoints.user.verify_password',
                return_value=(True, None),
            ),
        ):
            response = await self.client.post(
                '/api/v1/auth/login',
                json={
                    'login': '+7 999 123-45-67',
                    'password': 'correct-password',
                },
            )

        self.assertEqual(response.status_code, 200)
        get_by_login.assert_awaited_once_with(
            '+79991234567',
            self.session,
        )

    async def test_updated_password_hash_is_saved(self) -> None:
        """Обновлённый алгоритмом хеш сохраняется при успешном входе."""
        user = _make_user()

        with (
            patch(
                'api.endpoints.user.user_crud.get_by_login',
                new=AsyncMock(return_value=user),
            ),
            patch(
                'api.endpoints.user.verify_password',
                return_value=(True, 'updated-password-hash'),
            ),
        ):
            response = await self.client.post(
                '/api/v1/auth/login',
                json={
                    'login': 'tester@example.com',
                    'password': 'correct-password',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.hashed_password, 'updated-password-hash')
        self.session.commit.assert_awaited_once()

    async def test_wrong_password_returns_generic_error(self) -> None:
        """Неверный пароль не раскрывает причину отказа во входе."""
        user = _make_user()

        with (
            patch(
                'api.endpoints.user.user_crud.get_by_login',
                new=AsyncMock(return_value=user),
            ),
            patch(
                'api.endpoints.user.verify_password',
                return_value=(False, None),
            ),
        ):
            response = await self.client.post(
                '/api/v1/auth/login',
                json={
                    'login': 'tester@example.com',
                    'password': 'wrong-password',
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {
                'code': 422,
                'message': 'Неверные имя пользователя или пароль.',
            },
        )

    async def test_unknown_login_uses_dummy_hash(self) -> None:
        """Неизвестный логин всё равно выполняет проверку хеша."""
        verify = patch(
            'api.endpoints.user.verify_password',
            return_value=(False, None),
        )

        with (
            patch(
                'api.endpoints.user.user_crud.get_by_login',
                new=AsyncMock(return_value=None),
            ),
            verify as verify_password,
        ):
            response = await self.client.post(
                '/api/v1/auth/login',
                json={
                    'login': 'missing@example.com',
                    'password': 'any-password',
                },
            )

        self.assertEqual(response.status_code, 422)
        verify_password.assert_called_once_with(
            'any-password',
            DUMMY_PASSWORD_HASH,
        )

    async def test_inactive_user_cannot_login(self) -> None:
        """Правильный пароль не даёт токен неактивному пользователю."""
        user = _make_user(is_active=False)

        with (
            patch(
                'api.endpoints.user.user_crud.get_by_login',
                new=AsyncMock(return_value=user),
            ),
            patch(
                'api.endpoints.user.verify_password',
                return_value=(True, None),
            ),
        ):
            response = await self.client.post(
                '/api/v1/auth/login',
                json={
                    'login': 'inactive@example.com',
                    'password': 'correct-password',
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn('access_token', response.json())

    async def test_invalid_phone_is_rejected_before_database_lookup(self) -> None:
        """Некорректный телефон возвращает 422 без обращения к CRUD."""
        get_by_login = AsyncMock()

        with patch(
            'api.endpoints.user.user_crud.get_by_login',
            new=get_by_login,
        ):
            response = await self.client.post(
                '/api/v1/auth/login',
                json={
                    'login': '123',
                    'password': 'password',
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 422)
        get_by_login.assert_not_awaited()


class CurrentUserSessionTests(IsolatedAsyncioTestCase):
    """Проверяет таймаут неактивности JWT-сессии."""

    async def asyncSetUp(self) -> None:
        """Создаёт токен и зависимости проверки пользователя."""
        self.user = _make_user()
        self.token = create_access_token(self.user.id)
        self.credentials = HTTPAuthorizationCredentials(
            scheme='Bearer',
            credentials=self.token,
        )
        self.session = AsyncMock(spec=AsyncSession)
        self.session.get.return_value = self.user
        self.redis = AsyncMock()
        self.redis.getex.return_value = str(self.user.id)

    async def test_active_session_is_extended_after_request(self) -> None:
        """Успешная авторизация продлевает TTL сессии токена."""
        result = await get_current_user(
            self.credentials,
            self.session,
            self.redis,
        )

        self.assertIs(result, self.user)
        self.redis.getex.assert_awaited_once()
        redis_call = self.redis.getex.await_args
        self.assertTrue(redis_call.args[0].startswith(TOKEN_SESSION_KEY_PREFIX))
        self.assertEqual(
            redis_call.kwargs['ex'],
            settings.jwt_lifetime_seconds,
        )

    async def test_expired_session_is_rejected(self) -> None:
        """Отсутствующая в Redis сессия означает истёкший токен."""
        self.redis.getex.return_value = None

        with self.assertRaises(HTTPException) as error:
            await get_current_user(
                self.credentials,
                self.session,
                self.redis,
            )

        self.assertEqual(error.exception.status_code, 401)
        self.session.get.assert_not_awaited()

    async def test_binary_redis_value_is_supported(self) -> None:
        """Проверка работает и при отключённом decode_responses Redis."""
        self.redis.getex.return_value = str(self.user.id).encode()

        result = await get_current_user(
            self.credentials,
            self.session,
            self.redis,
        )

        self.assertIs(result, self.user)

    async def test_session_for_another_user_is_rejected(self) -> None:
        """Сессия не может быть использована с чужим subject токена."""
        self.redis.getex.return_value = str(uuid.uuid4())

        with self.assertRaises(HTTPException) as error:
            await get_current_user(
                self.credentials,
                self.session,
                self.redis,
            )

        self.assertEqual(error.exception.status_code, 401)
        self.session.get.assert_not_awaited()
