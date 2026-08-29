import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import ANY, AsyncMock, Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from api.endpoints.action import (  # noqa: E402
    create_action,
    get_action_by_id,
    get_all_actions,
    update_action,
)
from crud.action import ActionAlreadyExistsError, action_crud  # noqa: E402
from crud.base import CRUDBase  # noqa: E402
from main import app  # noqa: E402
from models.cafe import Cafe  # noqa: E402
from models.user import UserRole  # noqa: E402
from schemas.action import ActionCreate, ActionUpdate  # noqa: E402
from services.action import ensure_manager_cafe_access, get_action_or_raise  # noqa: E402
from services.errors import EntityNotFoundError, PermissionDeniedError  # noqa: E402


class ActionSchemaTests(TestCase):
    """Проверяет схемы и опубликованный контракт акций."""

    def test_create_requires_non_empty_cafes(self) -> None:
        """Акцию нельзя создать без кафе."""
        with self.assertRaises(ValidationError):
            ActionCreate(
                description='Скидка на завтрак',
                photo_id=None,
                cafes_id=[],
            )

    def test_update_allows_partial_payload(self) -> None:
        """PATCH принимает только изменяемые поля."""
        update = ActionUpdate(is_active=False)

        self.assertEqual(update.model_dump(exclude_unset=True), {'is_active': False})

    def test_generated_openapi_matches_actions_contract(self) -> None:
        """OpenAPI содержит нужные ручки и возвращает кафе объектами."""
        specification = app.openapi()
        collection_methods = specification['paths']['/actions']
        detail_methods = specification['paths']['/actions/{action_id}']

        self.assertEqual(set(collection_methods), {'get', 'post'})
        self.assertEqual(set(detail_methods), {'get', 'patch'})
        action_fields = specification['components']['schemas']['ActionInfo']['properties']
        self.assertIn('cafes', action_fields)
        self.assertNotIn('cafes_id', action_fields)
        create_schema = specification['components']['schemas']['ActionCreate']
        self.assertEqual(
            set(create_schema['required']),
            {'cafes_id', 'description', 'photo_id'},
        )


class ActionAccessTests(TestCase):
    """Проверяет ограничения менеджера на своё кафе."""

    def test_manager_cannot_attach_action_to_another_cafe(self) -> None:
        """Менеджер не может менять акции чужого кафе."""
        own_cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=own_cafe_id,
        )

        with self.assertRaises(PermissionDeniedError):
            ensure_manager_cafe_access(manager, [own_cafe_id, uuid.uuid4()])


class ActionEndpointTests(IsolatedAsyncioTestCase):
    """Проверяет ролевую логику ручек акций."""

    async def test_user_list_forces_active_filter(self) -> None:
        """Обычный пользователь видит только активные акции."""
        cafe_id = uuid.uuid4()
        user = SimpleNamespace(role=UserRole.USER, cafe_id=None)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.action.action_crud.get_all', new=get_all):
            result = await get_all_actions(
                user,
                AsyncMock(spec=AsyncSession),
                show_active=False,
                cafe_id=cafe_id,
            )

        self.assertEqual(result, [])
        get_all.assert_awaited_once_with(
            session=ANY,
            is_active=True,
            cafe_id=cafe_id,
        )

    async def test_manager_list_defaults_to_active_in_own_cafe(self) -> None:
        """Менеджер по умолчанию получает активные акции своего кафе."""
        own_cafe_id = uuid.uuid4()
        manager = SimpleNamespace(role=UserRole.MANAGER, cafe_id=own_cafe_id)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.action.action_crud.get_all', new=get_all):
            await get_all_actions(
                manager,
                AsyncMock(spec=AsyncSession),
                show_active=None,
                cafe_id=uuid.uuid4(),
            )

        get_all.assert_awaited_once_with(
            session=ANY,
            is_active=True,
            cafe_id=own_cafe_id,
        )

    async def test_manager_can_request_inactive_actions_in_own_cafe(self) -> None:
        """Менеджер может явно запросить отключённые акции своего кафе."""
        own_cafe_id = uuid.uuid4()
        manager = SimpleNamespace(role=UserRole.MANAGER, cafe_id=own_cafe_id)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.action.action_crud.get_all', new=get_all):
            await get_all_actions(
                manager,
                AsyncMock(spec=AsyncSession),
                show_active=False,
                cafe_id=None,
            )

        get_all.assert_awaited_once_with(
            session=ANY,
            is_active=False,
            cafe_id=own_cafe_id,
        )

    async def test_manager_without_cafe_gets_empty_list(self) -> None:
        """Менеджер без кафе не получает акции всех заведений."""
        manager = SimpleNamespace(role=UserRole.MANAGER, cafe_id=None)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.action.action_crud.get_all', new=get_all):
            result = await get_all_actions(
                manager,
                AsyncMock(spec=AsyncSession),
                show_active=None,
                cafe_id=None,
            )

        self.assertEqual(result, [])
        get_all.assert_not_awaited()

    async def test_create_checks_cafes_before_crud(self) -> None:
        """Создание сначала проверяет права и существование кафе."""
        cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=cafe_id,
        )
        payload = ActionCreate(
            description='Скидка на завтрак',
            photo_id=None,
            cafes_id=[cafe_id],
        )
        session = AsyncMock(spec=AsyncSession)
        redis = AsyncMock()
        ensure_cafes = AsyncMock()
        create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

        with (
            patch('api.endpoints.action.ensure_cafes_exist', new=ensure_cafes),
            patch('api.endpoints.action.action_crud.create', new=create),
        ):
            result = await create_action(payload, manager, session, redis)

        ensure_cafes.assert_awaited_once_with([cafe_id], session)
        create.assert_awaited_once_with(payload, session, redis)
        self.assertIs(result, create.return_value)

    async def test_user_cannot_get_inactive_action(self) -> None:
        """Неактивная акция скрыта от обычного пользователя как отсутствующая."""
        user = SimpleNamespace(role=UserRole.USER)
        action = SimpleNamespace(is_active=False)

        with self.assertRaises(HTTPException) as raised:
            await get_action_by_id(
                uuid.uuid4(),
                user,
                AsyncMock(spec=AsyncSession),
                action,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, 'Акция не найдена')

    async def test_update_uses_existing_cafes_when_not_replaced(self) -> None:
        """Частичное обновление сохраняет текущую привязку к кафе."""
        cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=cafe_id,
        )
        action = SimpleNamespace(
            id=uuid.uuid4(),
            cafes=[SimpleNamespace(id=cafe_id)],
        )
        payload = ActionUpdate(description='Новая скидка')
        session = AsyncMock(spec=AsyncSession)
        redis = AsyncMock()
        ensure_cafes = AsyncMock()
        update = AsyncMock(return_value=action)

        with (
            patch('api.endpoints.action.ensure_cafes_exist', new=ensure_cafes),
            patch('api.endpoints.action.action_crud.update', new=update),
        ):
            result = await update_action(
                action.id,
                payload,
                manager,
                session,
                redis,
                action,
            )

        ensure_cafes.assert_awaited_once_with([cafe_id], session)
        update.assert_awaited_once_with(action, payload, session, redis)
        self.assertIs(result, action)

    async def test_manager_cannot_move_foreign_action_to_own_cafe(self) -> None:
        """Нельзя захватить чужую акцию, сменив её список кафе."""
        own_cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=own_cafe_id,
        )
        action = SimpleNamespace(
            id=uuid.uuid4(),
            cafes=[SimpleNamespace(id=uuid.uuid4())],
        )
        payload = ActionUpdate(cafes_id=[own_cafe_id])
        update = AsyncMock()

        with patch('api.endpoints.action.action_crud.update', new=update):
            with self.assertRaises(PermissionDeniedError):
                await update_action(
                    action.id,
                    payload,
                    manager,
                    AsyncMock(spec=AsyncSession),
                    AsyncMock(),
                    action,
                )

        update.assert_not_awaited()


class ActionCrudTests(IsolatedAsyncioTestCase):
    """Проверяет запись акций и обработку конфликтов БД."""

    async def test_create_resolves_cafes_and_commits(self) -> None:
        """CRUD связывает акцию с переданными кафе и очищает кэш."""
        cafe_id = uuid.uuid4()
        cafe = Cafe(
            id=cafe_id,
            name='Кафе',
            address='Адрес',
            phone='+79991234567',
        )
        scalar_result = Mock()
        scalar_result.all.return_value = [cafe]
        query_result = Mock()
        query_result.scalars.return_value = scalar_result
        session = AsyncMock(spec=AsyncSession)
        session.add = Mock()
        session.execute.return_value = query_result
        redis = AsyncMock()
        payload = ActionCreate(
            description='Скидка на завтрак',
            photo_id=None,
            cafes_id=[cafe_id],
        )

        with patch.object(
            action_crud.response_schema,
            'model_validate',
            side_effect=lambda obj: obj,
        ):
            action = await action_crud.create(payload, session, redis)

        self.assertEqual(action.cafes, [cafe])
        self.assertEqual(action.description, payload.description)
        session.add.assert_called_once_with(action)
        session.commit.assert_awaited_once()
        redis.delete.assert_awaited_once_with(
            'actions:all',
            'actions:all:true',
            'actions:all:false',
        )

    async def test_create_turns_integrity_error_into_domain_error(self) -> None:
        """Конфликт уникальности не утекает из CRUD как SQLAlchemy ошибка."""
        session = AsyncMock(spec=AsyncSession)
        redis = AsyncMock()
        payload = ActionCreate(
            description='Повтор акции',
            photo_id=None,
            cafes_id=[uuid.uuid4()],
        )
        integrity_error = IntegrityError('INSERT', {}, Exception('duplicate'))

        with patch.object(
            CRUDBase,
            'create',
            new=AsyncMock(side_effect=integrity_error),
        ):
            with self.assertRaises(ActionAlreadyExistsError):
                await action_crud.create(payload, session, redis)

        session.rollback.assert_awaited_once()


class ActionServiceTests(IsolatedAsyncioTestCase):
    """Проверяет доменный поиск акции."""

    async def test_missing_action_raises_domain_error(self) -> None:
        """Неизвестный UUID превращается в понятную доменную ошибку."""
        action_id = uuid.uuid4()
        lookup = AsyncMock(return_value=None)

        with patch('services.action.action_crud.get', new=lookup):
            with self.assertRaises(EntityNotFoundError) as raised:
                await get_action_or_raise(
                    action_id,
                    AsyncMock(spec=AsyncSession),
                )

        lookup.assert_awaited_once()
        self.assertEqual(str(raised.exception), 'Акция не найдена')
