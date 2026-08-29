import os
import sys
import uuid
from decimal import Decimal
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

from api.endpoints.dish import (  # noqa: E402
    create_dish,
    get_all_dishes,
    get_dish_by_id,
    update_dish,
)
from crud.base import CRUDBase  # noqa: E402
from crud.dish import DishAlreadyExistsError, dish_crud  # noqa: E402
from main import app  # noqa: E402
from models.cafe import Cafe  # noqa: E402
from models.user import UserRole  # noqa: E402
from schemas.dish import DishCreate, DishUpdate  # noqa: E402
from services.dish import ensure_manager_cafe_access, get_dish_or_raise  # noqa: E402
from services.errors import EntityNotFoundError, PermissionDeniedError  # noqa: E402


class DishSchemaTests(TestCase):
    """Проверяет схемы и опубликованный контракт блюд."""

    def test_create_requires_non_empty_cafes(self) -> None:
        """Блюдо нельзя создать без кафе."""
        with self.assertRaises(ValidationError):
            DishCreate(
                name='Борщ',
                description='Свекольный суп',
                photo_id=None,
                price=Decimal('250.00'),
                cafes_id=[],
            )

    def test_update_allows_partial_payload(self) -> None:
        """PATCH принимает только изменяемые поля."""
        update = DishUpdate(is_active=False)

        self.assertEqual(update.model_dump(exclude_unset=True), {'is_active': False})

    def test_generated_openapi_matches_dishes_contract(self) -> None:
        """OpenAPI содержит нужные ручки и возвращает кафе объектами."""
        specification = app.openapi()
        collection_methods = specification['paths']['/dishes']
        detail_methods = specification['paths']['/dishes/{dish_id}']

        self.assertEqual(set(collection_methods), {'get', 'post'})
        self.assertEqual(set(detail_methods), {'get', 'patch'})
        dish_fields = specification['components']['schemas']['DishInfo']['properties']
        self.assertIn('cafes', dish_fields)
        self.assertNotIn('cafes_id', dish_fields)
        create_schema = specification['components']['schemas']['DishCreate']
        self.assertEqual(
            set(create_schema['required']),
            {'name', 'price'},
        )


class DishAccessTests(TestCase):
    """Проверяет ограничения менеджера на своё кафе."""

    def test_manager_cannot_attach_dish_to_another_cafe(self) -> None:
        """Менеджер не может менять блюда чужого кафе."""
        own_cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=own_cafe_id,
        )

        with self.assertRaises(PermissionDeniedError):
            ensure_manager_cafe_access(manager, [own_cafe_id, uuid.uuid4()])


class DishEndpointTests(IsolatedAsyncioTestCase):
    """Проверяет ролевую логику ручек блюд."""

    async def test_user_list_forces_active_filter(self) -> None:
        """Обычный пользователь видит только активные блюда."""
        cafe_id = uuid.uuid4()
        user = SimpleNamespace(role=UserRole.USER, cafe_id=None)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.dish.dish_crud.get_all', new=get_all):
            result = await get_all_dishes(
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
        """Менеджер по умолчанию получает активные блюда своего кафе."""
        own_cafe_id = uuid.uuid4()
        manager = SimpleNamespace(role=UserRole.MANAGER, cafe_id=own_cafe_id)
        get_all = AsyncMock(return_value=[])

        with patch('api.endpoints.dish.dish_crud.get_all', new=get_all):
            await get_all_dishes(
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

    async def test_create_checks_cafes_before_crud(self) -> None:
        """Создание сначала проверяет права и существование кафе."""
        cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=cafe_id,
        )
        payload = DishCreate(
            name='Борщ',
            description='Свекольный суп',
            photo_id=None,
            price=Decimal('250.00'),
            cafes_id=[cafe_id],
        )
        session = AsyncMock(spec=AsyncSession)
        redis = AsyncMock()
        ensure_cafes = AsyncMock()
        create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

        with (
            patch('api.endpoints.dish.ensure_cafes_exist', new=ensure_cafes),
            patch('api.endpoints.dish.dish_crud.create', new=create),
        ):
            result = await create_dish(payload, manager, session, redis)

        ensure_cafes.assert_awaited_once_with([cafe_id], session)
        create.assert_awaited_once_with(payload, session, redis)
        self.assertIs(result, create.return_value)

    async def test_user_cannot_get_inactive_dish(self) -> None:
        """Неактивное блюдо скрыто от обычного пользователя как отсутствующее."""
        user = SimpleNamespace(role=UserRole.USER)
        dish = SimpleNamespace(is_active=False)

        with self.assertRaises(HTTPException) as raised:
            await get_dish_by_id(
                uuid.uuid4(),
                user,
                AsyncMock(spec=AsyncSession),
                dish,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, 'Блюдо не найдено')

    async def test_update_uses_existing_cafes_when_not_replaced(self) -> None:
        """Частичное обновление сохраняет текущую привязку к кафе."""
        cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=cafe_id,
        )
        dish = SimpleNamespace(
            id=uuid.uuid4(),
            cafes=[SimpleNamespace(id=cafe_id)],
        )
        payload = DishUpdate(name='Новый борщ')
        session = AsyncMock(spec=AsyncSession)
        redis = AsyncMock()
        ensure_cafes = AsyncMock()
        update = AsyncMock(return_value=dish)

        with (
            patch('api.endpoints.dish.ensure_cafes_exist', new=ensure_cafes),
            patch('api.endpoints.dish.dish_crud.update', new=update),
        ):
            result = await update_dish(
                dish.id,
                payload,
                manager,
                session,
                redis,
                dish,
            )

        ensure_cafes.assert_awaited_once_with([cafe_id], session)
        update.assert_awaited_once_with(dish, payload, session, redis)
        self.assertIs(result, dish)

    async def test_manager_cannot_attach_dish_to_foreign_cafe(self) -> None:
        """Менеджер не может указать чужое кафе в payload при обновлении."""
        own_cafe_id = uuid.uuid4()
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=own_cafe_id,
        )
        dish = SimpleNamespace(
            id=uuid.uuid4(),
            cafes=[SimpleNamespace(id=own_cafe_id)],
        )
        payload = DishUpdate(cafes_id=[uuid.uuid4()])
        update = AsyncMock()

        with patch('api.endpoints.dish.dish_crud.update', new=update):
            with self.assertRaises(PermissionDeniedError):
                await update_dish(
                    dish.id,
                    payload,
                    manager,
                    AsyncMock(spec=AsyncSession),
                    AsyncMock(),
                    dish,
                )

        update.assert_not_awaited()


class DishCrudTests(IsolatedAsyncioTestCase):
    """Проверяет запись блюд и обработку конфликтов БД."""

    async def test_create_resolves_cafes_and_commits(self) -> None:
        """CRUD связывает блюдо с переданными кафе и очищает кэш."""
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
        payload = DishCreate(
            name='Борщ',
            description='Свекольный суп',
            photo_id=None,
            price=Decimal('250.00'),
            cafes_id=[cafe_id],
        )

        with patch.object(
            dish_crud.response_schema,
            'model_validate',
            side_effect=lambda obj: obj,
        ):
            dish = await dish_crud.create(payload, session, redis)

        self.assertEqual(dish.cafes, [cafe])
        self.assertEqual(dish.name, payload.name)
        session.add.assert_called_once_with(dish)
        session.commit.assert_awaited_once()
        redis.delete.assert_awaited_once_with(
            'dishes:all',
            'dishes:all:true',
            'dishes:all:false',
        )

    async def test_create_turns_integrity_error_into_domain_error(self) -> None:
        """Конфликт уникальности не утекает из CRUD как SQLAlchemy ошибка."""
        session = AsyncMock(spec=AsyncSession)
        redis = AsyncMock()
        payload = DishCreate(
            name='Повтор блюда',
            description=None,
            photo_id=None,
            price=Decimal('100.00'),
            cafes_id=[uuid.uuid4()],
        )
        integrity_error = IntegrityError('INSERT', {}, Exception('duplicate'))

        with patch.object(
            CRUDBase,
            'create',
            new=AsyncMock(side_effect=integrity_error),
        ):
            with self.assertRaises(DishAlreadyExistsError):
                await dish_crud.create(payload, session, redis)

        session.rollback.assert_awaited_once()


class DishServiceTests(IsolatedAsyncioTestCase):
    """Проверяет доменный поиск блюда."""

    async def test_missing_dish_raises_domain_error(self) -> None:
        """Неизвестный UUID превращается в понятную доменную ошибку."""
        dish_id = uuid.uuid4()
        lookup = AsyncMock(return_value=None)

        with patch('services.dish.dish_crud.get', new=lookup):
            with self.assertRaises(EntityNotFoundError) as raised:
                await get_dish_or_raise(
                    dish_id,
                    AsyncMock(spec=AsyncSession),
                )

        lookup.assert_awaited_once()
        self.assertEqual(str(raised.exception), 'Блюдо не найдено')
