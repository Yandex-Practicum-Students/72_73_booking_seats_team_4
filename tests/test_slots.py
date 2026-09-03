import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, time, timezone
from types import SimpleNamespace
from typing import Never
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.cafe import get_cafe_or_404
from api.dependencies.logging import get_current_user_with_logging
from api.dependencies.slots import get_slot_in_cafe
from crud.slot import slot_crud
from exceptions.common import EntityNotFoundError
from main import app
from models.user import UserRole
from schemas.slots import TimeSlotCreate
from tests.test_cafes_api import _make_cafe, _make_user

from core.db import get_session
from core.redis import get_redis_session


def _make_slot(
    *,
    slot_id: uuid.UUID | None = None,
    cafe_id: uuid.UUID,
    start_time: time | None = None,
    end_time: time | None = None,
    is_active: bool = True,
    description: str | None = None,
) -> SimpleNamespace:
    """Создаёт объект слота, совместимый с TimeSlotInfo."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=slot_id or uuid.uuid4(),
        cafe_id=cafe_id,
        start_time=start_time or time(10, 0),
        end_time=end_time or time(12, 0),
        description=description or 'Тестовый слот',
        is_active=is_active,
        created_at=now,
        updated_at=now,
        cafe=_make_cafe(cafe_id=cafe_id),
    )


class SlotAPIContractTests(TestCase):
    """Проверяет опубликованный контракт ручек слотов."""

    def test_slots_routes_match_specification(self) -> None:
        """Коллекция и объект слотов публикуют только заявленные методы."""
        paths = app.openapi()['paths']

        self.assertEqual(set(paths['/api/v1/cafes/{cafe_id}/time_slots']), {'get', 'post'})
        self.assertEqual(set(paths['/api/v1/cafes/{cafe_id}/time_slots/{slot_id}']), {'get', 'patch'})


class SlotAPITests(IsolatedAsyncioTestCase):
    """Проверяет HTTP-контракт и права доступа ручек слотов."""

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

    @staticmethod
    def _set_slot(slot: SimpleNamespace) -> None:
        """Подменяет получение слота по идентификатору."""

        async def slot_override() -> SimpleNamespace:
            return slot

        app.dependency_overrides[get_slot_in_cafe] = slot_override

    async def test_admin_list_passes_activity_filter_to_crud(self) -> None:
        """Администратор может запросить только неактивные слоты."""
        slot = _make_slot(cafe_id=self.cafe_id, is_active=False)
        get_by_cafe = AsyncMock(return_value=[slot])

        with patch('api.endpoints.slots.slot_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
                params={'show_active': 'false'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['id'], str(slot.id))
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

        with patch('api.endpoints.slots.slot_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
            )

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

    async def test_regular_user_always_gets_only_active_slots(self) -> None:
        """Пользователь не может снять серверный фильтр активности."""
        self._set_user(_make_user(UserRole.USER))
        slot = _make_slot(cafe_id=self.cafe_id)
        get_by_cafe = AsyncMock(return_value=[slot])

        with patch('api.endpoints.slots.slot_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
                params={'show_active': 'false'},
            )

        self.assertEqual(response.status_code, 200)
        get_by_cafe.assert_awaited_once_with(
            cafe_id=self.cafe_id,
            session=self.session,
            show_active=True,
        )

    async def test_manager_gets_active_slots_by_default_in_own_cafe(self) -> None:
        """Менеджер по умолчанию видит только активные слоты своего кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=self.cafe_id)
        self._set_user(manager)
        slot = _make_slot(cafe_id=self.cafe_id)
        get_by_cafe = AsyncMock(return_value=[slot])

        with patch('api.endpoints.slots.slot_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
            )

        self.assertEqual(response.status_code, 200)
        get_by_cafe.assert_awaited_once_with(
            cafe_id=self.cafe_id,
            session=self.session,
            show_active=True,
        )

    async def test_manager_cannot_request_inactive_slots_in_own_cafe(self) -> None:
        """Менеджер всегда видит только активные слоты своего кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=self.cafe_id)
        self._set_user(manager)
        slot = _make_slot(cafe_id=self.cafe_id, is_active=False)
        get_by_cafe = AsyncMock(return_value=[slot])

        with patch('api.endpoints.slots.slot_crud.get_by_cafe', new=get_by_cafe):
            response = await self.client.get(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
                params={'show_active': 'false'},
            )

        self.assertEqual(response.status_code, 200)
        get_by_cafe.assert_awaited_once_with(
            cafe_id=self.cafe_id,
            session=self.session,
            show_active=True,
        )

    async def test_admin_can_create_slot(self) -> None:
        """POST /cafes/{cafe_id}/time_slots возвращает 201."""
        slot = _make_slot(cafe_id=self.cafe_id)
        create_with_cafe = AsyncMock(return_value=slot)
        payload = {
            'start_time': '10:00',
            'end_time': '12:00',
            'description': 'Тестовый слот',
        }

        with patch(
            'api.endpoints.slots.slot_crud.create_with_cafe',
            new=create_with_cafe,
        ):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
                json=payload,
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], str(slot.id))
        create_with_cafe.assert_awaited_once()
        cafe_id, request_schema, session = create_with_cafe.await_args.args
        self.assertEqual(cafe_id, self.cafe_id)
        self.assertEqual(request_schema.start_time, time(10, 0))
        self.assertEqual(request_schema.end_time, time(12, 0))
        self.assertIs(session, self.session)

    async def test_slot_creation_validates_time_range(self) -> None:
        """Создание слота проверяет, что start_time < end_time."""
        create_with_cafe = AsyncMock()

        with patch(
            'api.endpoints.slots.slot_crud.create_with_cafe',
            new=create_with_cafe,
        ):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
                json={
                    'start_time': '12:00',
                    'end_time': '10:00',
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn(
            'Время начала должно быть меньше времени окончания',
            response.json()['message'],
        )
        create_with_cafe.assert_not_awaited()

    async def test_regular_user_cannot_create_slot(self) -> None:
        """Создание слота запрещено обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        create_with_cafe = AsyncMock()

        with patch(
            'api.endpoints.slots.slot_crud.create_with_cafe',
            new=create_with_cafe,
        ):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
                json={
                    'start_time': '10:00',
                    'end_time': '12:00',
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Доступ запрещён.'},
        )
        create_with_cafe.assert_not_awaited()

    async def test_user_can_get_active_slot_by_id(self) -> None:
        """Активный слот доступен обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        slot = _make_slot(cafe_id=self.cafe_id)
        self._set_slot(slot)

        response = await self.client.get(
            f'/api/v1/cafes/{self.cafe_id}/time_slots/{slot.id}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(slot.id))

    async def test_inactive_slot_is_hidden_from_regular_user(self) -> None:
        """Неактивный слот выглядит для пользователя как отсутствующий."""
        self._set_user(_make_user(UserRole.USER))
        slot = _make_slot(cafe_id=self.cafe_id, is_active=False)
        self._set_slot(slot)

        response = await self.client.get(
            f'/api/v1/cafes/{self.cafe_id}/time_slots/{slot.id}',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {'code': 404, 'message': 'Слот не найден'},
        )

    async def test_admin_can_get_inactive_slot_by_id(self) -> None:
        """Администратор может получить неактивный слот."""
        slot = _make_slot(cafe_id=self.cafe_id, is_active=False)
        self._set_slot(slot)

        response = await self.client.get(
            f'/api/v1/cafes/{self.cafe_id}/time_slots/{slot.id}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(slot.id))
        self.assertFalse(response.json()['is_active'])

    async def test_missing_cafe_uses_custom_error_response(self) -> None:
        """Неизвестный UUID возвращает единый формат ошибки 404."""

        async def missing_cafe() -> Never:
            raise EntityNotFoundError('Кафе не найдено')

        app.dependency_overrides[get_cafe_or_404] = missing_cafe

        response = await self.client.get(
            f'/api/v1/cafes/{uuid.uuid4()}/time_slots',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {'code': 404, 'message': 'Кафе не найдено'},
        )

    async def test_manager_cannot_get_slot_in_foreign_cafe(self) -> None:
        """Менеджер получает 403 при обращении к слоту чужого кафе."""
        foreign_cafe_id = uuid.uuid4()
        manager = _make_user(UserRole.MANAGER, cafe_id=self.cafe_id)
        self._set_user(manager)
        self._set_cafe(_make_cafe(cafe_id=foreign_cafe_id))
        slot = _make_slot(cafe_id=foreign_cafe_id)
        self._set_slot(slot)

        response = await self.client.get(
            f'/api/v1/cafes/{foreign_cafe_id}/time_slots/{slot.id}',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Менеджер может управлять только своим кафе'},
        )

    async def test_manager_can_create_slot_in_own_cafe(self) -> None:
        """Менеджер может создавать слоты в своём кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=self.cafe_id)
        self._set_user(manager)
        slot = _make_slot(cafe_id=self.cafe_id)
        create_with_cafe = AsyncMock(return_value=slot)
        payload = {
            'start_time': '10:00',
            'end_time': '12:00',
            'description': 'Тестовый слот',
        }

        with patch('api.endpoints.slots.slot_crud.create_with_cafe', new=create_with_cafe):
            response = await self.client.post(
                f'/api/v1/cafes/{self.cafe_id}/time_slots',
                json=payload,
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], str(slot.id))
        create_with_cafe.assert_awaited_once()

    async def test_manager_can_update_slot_in_own_cafe(self) -> None:
        """Менеджер может обновить слот в своём кафе."""
        manager = _make_user(UserRole.MANAGER, cafe_id=self.cafe_id)
        self._set_user(manager)
        slot = _make_slot(cafe_id=self.cafe_id)
        updated_slot = _make_slot(
            cafe_id=self.cafe_id,
            start_time=time(14, 0),
            end_time=time(16, 0),
            description='Обновлённый слот',
        )
        self._set_slot(slot)
        update = AsyncMock(return_value=updated_slot)

        with patch('api.endpoints.slots.slot_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{self.cafe_id}/time_slots/{slot.id}',
                json={
                    'start_time': '14:00',
                    'end_time': '16:00',
                    'description': 'Обновлённый слот',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(updated_slot.id))
        update.assert_awaited_once()

    async def test_admin_can_update_slot(self) -> None:
        """PATCH /cafes/{cafe_id}/time_slots/{slot_id} обновляет слот."""
        slot = _make_slot(cafe_id=self.cafe_id)
        updated_slot = _make_slot(
            cafe_id=self.cafe_id,
            start_time=time(14, 0),
            end_time=time(16, 0),
            description='Обновлённый слот',
        )
        self._set_slot(slot)
        update = AsyncMock(return_value=updated_slot)

        with patch('api.endpoints.slots.slot_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{self.cafe_id}/time_slots/{slot.id}',
                json={
                    'start_time': '14:00',
                    'end_time': '16:00',
                    'description': 'Обновлённый слот',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(updated_slot.id))
        self.assertEqual(response.json()['start_time'], '14:00:00')
        self.assertEqual(response.json()['end_time'], '16:00:00')
        update.assert_awaited_once()
        db_slot, request_schema, session, redis = update.await_args.args
        self.assertIs(db_slot, slot)
        self.assertEqual(request_schema.start_time, time(14, 0))
        self.assertEqual(request_schema.end_time, time(16, 0))
        self.assertIs(session, self.session)
        self.assertIs(redis, self.redis)

    async def test_regular_user_cannot_update_slot(self) -> None:
        """Обновление слота запрещено обычному пользователю."""
        self._set_user(_make_user(UserRole.USER))
        slot = _make_slot(cafe_id=self.cafe_id)
        self._set_slot(slot)
        update = AsyncMock()

        with patch('api.endpoints.slots.slot_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{self.cafe_id}/time_slots/{slot.id}',
                json={'description': 'Недоступное обновление'},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Доступ запрещён.'},
        )
        update.assert_not_awaited()

    async def test_manager_cannot_update_slot_in_foreign_cafe(self) -> None:
        """Менеджер не может обновлять слоты чужого кафе."""
        foreign_cafe_id = uuid.uuid4()
        manager = _make_user(UserRole.MANAGER, cafe_id=self.cafe_id)
        self._set_user(manager)
        self._set_cafe(_make_cafe(cafe_id=foreign_cafe_id))
        slot = _make_slot(cafe_id=foreign_cafe_id)
        self._set_slot(slot)
        update = AsyncMock()

        with patch('api.endpoints.slots.slot_crud.update', new=update):
            response = await self.client.patch(
                f'/api/v1/cafes/{foreign_cafe_id}/time_slots/{slot.id}',
                json={'description': 'Недоступное обновление'},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {'code': 403, 'message': 'Менеджер может управлять только своим кафе'},
        )
        update.assert_not_awaited()


class SlotCRUDTests(IsolatedAsyncioTestCase):
    """Проверяет CRUD-операции для слотов."""

    async def test_create_with_cafe_uses_cafe_id_from_url(self) -> None:
        """create_with_cafe использует cafe_id из URL, а не из тела запроса."""
        cafe_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        obj_in = TimeSlotCreate(
            start_time=time(10, 0),
            end_time=time(12, 0),
            description='Тестовый слот',
        )

        mock_slot = _make_slot(cafe_id=cafe_id, start_time=time(10, 0), end_time=time(12, 0))

        with patch.object(slot_crud, 'get', new=AsyncMock(return_value=mock_slot)):
            result = await slot_crud.create_with_cafe(cafe_id, obj_in, session)

        self.assertEqual(result.cafe_id, cafe_id)
        self.assertEqual(result.start_time, time(10, 0))
        self.assertEqual(result.end_time, time(12, 0))
        session.add.assert_called_once()
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()

    async def test_get_by_cafe_filters_by_show_active(self) -> None:
        """get_by_cafe корректно фильтрует по show_active."""
        cafe_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_slot(cafe_id=cafe_id, is_active=True),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        result = await slot_crud.get_by_cafe(cafe_id, session, show_active=True)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].is_active)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_slot(cafe_id=cafe_id, is_active=False),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        result = await slot_crud.get_by_cafe(cafe_id, session, show_active=False)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].is_active)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_slot(cafe_id=cafe_id, is_active=True),
            _make_slot(cafe_id=cafe_id, is_active=False),
        ]
        session.execute = AsyncMock(return_value=mock_result)

        result = await slot_crud.get_by_cafe(cafe_id, session, show_active=None)
        self.assertEqual(len(result), 2)

    async def test_get_by_cafe_and_id_checks_cafe_ownership(self) -> None:
        """get_by_cafe_and_id возвращает слот только если он принадлежит кафе."""
        cafe_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        session = AsyncMock(spec=AsyncSession)

        slot = _make_slot(cafe_id=cafe_id, slot_id=slot_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = slot
        session.execute = AsyncMock(return_value=mock_result)

        result = await slot_crud.get_by_cafe_and_id(cafe_id, slot_id, session)
        self.assertIs(result, slot)

        mock_result.scalar_one_or_none.return_value = None
        result = await slot_crud.get_by_cafe_and_id(cafe_id, slot_id, session)
        self.assertIsNone(result)
