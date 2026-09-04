import json
import uuid
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from api.dependencies.permissions import get_staff_user
from api.exceptions import api_error_handler
from crud.cafe import cafe_crud
from crud.user import user_crud
from exceptions.base import APIError
from main import app
from models.user import User, UserRole
from schemas.cafe import CafeCreate
from schemas.user import UserCreate

from core.db import get_session
from core.user import verify_password


class AsyncSessionContext:
    """Минимальный async context manager для проверки get_session."""

    def __init__(self, session: AsyncMock) -> None:
        """Сохраняет подменённую сессию и состояние выхода."""
        self.session = session
        self.exited = False

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *_: object) -> None:
        self.exited = True


class BackendFoundationTests(IsolatedAsyncioTestCase):
    """Проверяет общие ошибки, транзакции и CRUD-операции."""

    async def test_permission_error_uses_custom_error_format(self) -> None:
        """Permissions возвращают код и сообщение по спецификации."""
        user = SimpleNamespace(role=UserRole.USER)

        with self.assertRaises(APIError) as raised:
            await get_staff_user(user)

        response = await api_error_handler(None, raised.exception)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            json.loads(response.body),
            {'code': 403, 'message': 'Доступ запрещён.'},
        )

    async def test_get_session_commits_and_context_closes_session(self) -> None:
        """Успешная зависимость коммитит и закрывается контекстным менеджером."""
        session = AsyncMock()
        context = AsyncSessionContext(session)

        with patch('core.db.session_maker', return_value=context):
            dependency = get_session()
            yielded_session = await anext(dependency)
            self.assertIs(yielded_session, session)
            with self.assertRaises(StopAsyncIteration):
                await anext(dependency)

        session.commit.assert_awaited_once()
        self.assertTrue(context.exited)

    async def test_get_session_rolls_back_database_error(self) -> None:
        """Ошибка SQLAlchemy откатывает транзакцию и закрывает контекст."""
        session = AsyncMock()
        context = AsyncSessionContext(session)

        with patch('core.db.session_maker', return_value=context):
            dependency = get_session()
            await anext(dependency)
            with self.assertRaises(HTTPException) as raised:
                await dependency.athrow(SQLAlchemyError('database error'))

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(raised.exception.detail, 'Ошибка при работе с БД')
        session.rollback.assert_awaited_once()
        self.assertTrue(context.exited)

    async def test_user_create_commits_and_hashes_password(self) -> None:
        """UserCRUD явно коммитит и не сохраняет пароль открытым текстом."""
        session = AsyncMock()
        session.add = Mock()
        session.scalar.return_value = None
        source_password = 'strong-password'

        user = await user_crud.create(
            UserCreate(
                username='Tester',
                phone='+79991234567',
                password=source_password,
            ),
            session,
        )

        session.add.assert_called_once_with(user)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(user)
        self.assertNotEqual(user.hashed_password, source_password)
        self.assertTrue(verify_password(source_password, user.hashed_password)[0])

    async def test_user_update_commits_normalized_data(self) -> None:
        """UserCRUD нормализует обновление и явно фиксирует его."""
        user = SimpleNamespace(
            id=uuid.uuid4(),
            username='old-name',
            email='old@example.com',
            phone=None,
            tg_id=None,
        )
        session = AsyncMock()
        session.scalar.return_value = None

        result = await user_crud.update(
            user,
            {'username': '  NewName  ', 'email': 'NEW@EXAMPLE.COM'},
            session,
        )

        self.assertIs(result, user)
        self.assertEqual(user.username, 'NewName')
        self.assertEqual(user.email, 'new@example.com')
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(user)

    async def test_cafe_create_resolves_managers_and_commits(self) -> None:
        """CafeCRUD связывает менеджеров по UUID и коммитит создание."""
        manager_id = uuid.uuid4()
        manager = User(
            id=manager_id,
            username='manager',
            email='manager@example.com',
            hashed_password='hash',
            role=UserRole.MANAGER,
        )
        scalar_result = Mock()
        scalar_result.all.return_value = [manager]
        query_result = Mock()
        query_result.scalars.return_value = scalar_result
        session = AsyncMock()
        session.add = Mock()
        session.execute.return_value = query_result
        redis = AsyncMock()

        async def get_created_cafe(*_: object, **__: object) -> object:
            return session.add.call_args.args[0]

        with (
            patch.object(cafe_crud.response_schema, 'model_validate', side_effect=lambda obj: obj),
            patch.object(
                cafe_crud,
                'get',
                new=AsyncMock(side_effect=get_created_cafe),
            ),
        ):
            cafe = await cafe_crud.create(
                CafeCreate(
                    name='Cafe',
                    address='Address',
                    phone='+79991234567',
                    managers_id=[manager_id],
                ),
                session,
                redis,
            )

        self.assertEqual(cafe.managers, [manager])
        session.add.assert_called_once_with(cafe)
        session.commit.assert_awaited_once()
        redis.delete.assert_awaited_once_with(
            'cafes:all',
            'cafes:all:true',
            'cafes:all:false',
        )

    async def test_get_all_cache_uses_activity_filter(self) -> None:
        """Кэш списков разделён по фильтру активности."""
        session = AsyncMock()
        redis = AsyncMock()
        redis.get.return_value = None

        with patch('crud.base.CRUDBase.get_all', new=AsyncMock(return_value=[])) as get_all:
            result = await cafe_crud.get_all_with_cache(
                session=session,
                redis=redis,
                is_active=True,
            )

        self.assertEqual(result, [])
        redis.get.assert_awaited_once_with('cafes:all:true')
        get_all.assert_awaited_once_with(
            cafe_crud,
            session=session,
            is_active=True,
            options=None,
        )

    async def test_get_all_cache_falls_back_to_database(self) -> None:
        """Недоступный Redis не скрывает данные из Postgres."""
        session = AsyncMock()
        redis = AsyncMock()
        redis.get.side_effect = RedisError('redis unavailable')

        with patch('crud.base.CRUDBase.get_all', new=AsyncMock(return_value=[])) as get_all:
            result = await cafe_crud.get_all_with_cache(
                session=session,
                redis=redis,
                is_active=False,
            )

        self.assertEqual(result, [])
        get_all.assert_awaited_once_with(
            cafe_crud,
            session=session,
            is_active=False,
            options=None,
        )

    def test_generated_openapi_matches_delete_and_dish_contract(self) -> None:
        """В публичном API нет DELETE, а DishInfo возвращает cafes."""
        specification = app.openapi()

        self.assertFalse(
            any('delete' in methods for methods in specification['paths'].values()),
        )
        dish_fields = specification['components']['schemas']['DishInfo']['properties']
        self.assertIn('cafes', dish_fields)
        self.assertNotIn('cafes_id', dish_fields)

    def test_openapi_uses_project_metadata_and_versioned_paths(self) -> None:
        """Документация содержит данные проекта и публикует API v1."""
        specification = app.openapi()

        self.assertEqual(
            specification['info']['title'],
            'Система бронирования мест в кафе',
        )
        self.assertEqual(specification['info']['version'], '0.0.3')
        self.assertTrue(specification['info']['description'])
        self.assertTrue(
            all(path == '/' or path.startswith('/api/v1/') for path in specification['paths']),
        )
