import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.dish import get_dish_or_404
from api.dependencies.logging import get_current_user_with_logging
from main import app
from models.user import UserRole

from core.db import get_session
from core.redis import get_redis_session


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


def _make_dish(
    *,
    dish_id: uuid.UUID | None = None,
    name: str = 'Борщ',
    is_active: bool = True,
) -> SimpleNamespace:
    """Создаёт объект, совместимый с DishInfo."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=dish_id or uuid.uuid4(),
        name=name,
        description='Свекольный суп',
        photo_id=None,
        price=Decimal('250.00'),
        cafes=[],
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


class DishAPIContractTests(TestCase):
    """Проверяет опубликованный контракт ручек блюд."""

    def test_dishes_routes_match_specification(self) -> None:
        """Коллекция и объект блюда публикуют только заявленные методы."""
        paths = app.openapi()['paths']

        self.assertEqual(set(paths['/api/v1/dishes']), {'get', 'post'})
        self.assertEqual(set(paths['/api/v1/dishes/{dish_id}']), {'get', 'patch'})


class DishAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP-контракт и права доступа ручек /dishes."""

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
    def _set_dish(dish: SimpleNamespace) -> None:
        """Подменяет получение блюда по идентификатору."""

        async def dish_override() -> SimpleNamespace:
            return dish

        app.dependency_overrides[get_dish_or_404] = dish_override

    async def test_admin_list_passes_activity_filter_to_crud(self) -> None:
        """Администратор может запросить только неактивные блюда."""
        dish = _make_dish(is_active=False)
        get_all = AsyncMock(return_value=[dish])

        with patch('api.endpoints.dish.dish_crud.get_all', new=get_all):
            response = await self.client.get('/api/v1/dishes', params={'show_active': 'false'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(dish.id))
        self.assertFalse(response.json()[0]['is_active'])
        get_all.assert_awaited_once_with(
            session=self.session,
            is_active=False,
            cafe_id=None,
        )

    async def test_list_requires_authentication(self) -> None:
        """Запрос без Bearer-токена получает единый ответ 401."""
        app.dependency_overrides.pop(get_current_user_with_logging)
        get_all = AsyncMock()

        with patch('api.endpoints.dish.dish_crud.get_all', new=get_all):
            response = await self.client.get('/api/v1/dishes')

        self.assertEqual(response.status_code, 401)
        get_all.assert_not_awaited()

    async def test_regular_user_always_gets_only_active_dishes(self) -> None:
        """Пользователь не может снять серверный фильтр активности."""
        self._set_user(_make_user(UserRole.USER))
        dish = _make_dish()
        get_all = AsyncMock(return_value=[dish])

        with patch('api.endpoints.dish.dish_crud.get_all', new=get_all):
            response = await self.client.get('/api/v1/dishes', params={'show_active': 'false'})

        self.assertEqual(response.status_code, 200)
        get_all.assert_awaited_once_with(
            session=self.session,
            is_active=True,
            cafe_id=None,
        )

    async def test_manager_gets_only_own_cafe_dishes(self) -> None:
        """Менеджер видит только блюда своего кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=uuid.uuid4())
        self._set_user(manager)
        dish = _make_dish()
        get_all = AsyncMock(return_value=[dish])

        with patch('api.endpoints.dish.dish_crud.get_all', new=get_all):
            response = await self.client.get('/api/v1/dishes')

        self.assertEqual(response.status_code, 200)
        get_all.assert_awaited_once_with(
            session=self.session,
            is_active=True,
            cafe_id=manager.cafe_id,
        )

    async def test_admin_can_create_dish(self) -> None:
        """POST /dishes возвращает 201 и передаёт данные в CRUD."""
        dish = _make_dish()
        cafe_id = uuid.uuid4()
        create = AsyncMock(return_value=dish)
        payload = {
            'name': dish.name,
            'description': dish.description,
            'photo_id': None,
            'price': '250.00',
            'cafes_id': [str(cafe_id)],
        }

        with patch('api.endpoints.dish.create_dish_service', new=create):
            response = await self.client.post('/api/v1/dishes', json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], dish.name)
        create.assert_awaited_once()
        request_schema, current_user, session, redis = create.await_args.args
        self.assertEqual(request_schema.name, dish.name)
        self.assertEqual(request_schema.cafes_id, [cafe_id])
        self.assertEqual(current_user.role, UserRole.ADMIN)
        self.assertIs(session, self.session)
        self.assertIs(redis, self.redis)

    async def test_regular_user_cannot_create_dish(self) -> None:
        """Создание блюда запрещено обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        create = AsyncMock()

        with patch('api.endpoints.dish.create_dish_service', new=create):
            response = await self.client.post(
                '/api/v1/dishes',
                json={
                    'name': 'Новое блюдо',
                    'price': '100.00',
                    'cafes_id': [str(uuid.uuid4())],
                },
            )

        self.assertEqual(response.status_code, 403)
        create.assert_not_awaited()

    async def test_user_can_get_active_dish_by_id(self) -> None:
        """Активное блюдо доступно обычному пользователю."""
        dish = _make_dish()
        self._set_user(_make_user(UserRole.USER))
        self._set_dish(dish)

        response = await self.client.get(f'/api/v1/dishes/{dish.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(dish.id))

    async def test_inactive_dish_is_hidden_from_regular_user(self) -> None:
        """Неактивное блюдо выглядит для пользователя как отсутствующее."""
        dish = _make_dish(is_active=False)
        self._set_user(_make_user(UserRole.USER))
        self._set_dish(dish)

        response = await self.client.get(f'/api/v1/dishes/{dish.id}')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {'code': 404, 'message': 'Блюдо не найдено'},
        )

    async def test_admin_can_update_dish(self) -> None:
        """PATCH /dishes/{id} возвращает 200 и передаёт данные в CRUD."""
        dish = _make_dish()
        self._set_dish(dish)
        update = AsyncMock(return_value=dish)

        with patch('api.endpoints.dish.update_dish_service', new=update):
            response = await self.client.patch(
                f'/api/v1/dishes/{dish.id}',
                json={'name': 'Новый борщ'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], dish.name)
        update.assert_awaited_once()
        db_obj, request_schema, current_user, session, redis = update.await_args.args
        self.assertIs(db_obj, dish)
        self.assertEqual(request_schema.name, 'Новый борщ')
        self.assertEqual(current_user.role, UserRole.ADMIN)
        self.assertIs(session, self.session)
        self.assertIs(redis, self.redis)

    async def test_regular_user_cannot_update_dish(self) -> None:
        """Обновление блюда запрещено обычному пользователю."""
        dish = _make_dish()
        self._set_user(_make_user(UserRole.USER))
        self._set_dish(dish)
        update = AsyncMock()

        with patch('api.endpoints.dish.update_dish_service', new=update):
            response = await self.client.patch(
                f'/api/v1/dishes/{dish.id}',
                json={'name': 'Новый борщ'},
            )

        self.assertEqual(response.status_code, 403)
        update.assert_not_awaited()
