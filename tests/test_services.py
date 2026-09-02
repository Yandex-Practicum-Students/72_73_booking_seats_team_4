import uuid
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

from models.user import UserRole
from services.cafe import (
    ensure_cafes_exist,
    ensure_manager_cafe_access,
    ensure_manager_cafes_access,
    get_cafe_or_raise,
    get_manager_cafes,
)
from services.errors import EntityNotFoundError, PermissionDeniedError
from services.slot import get_slot_in_cafe_or_raise


class ServiceAccessTests(TestCase):
    """Тесты бизнес-прав доступа сервисного слоя."""

    def test_manager_cannot_access_another_cafe(self) -> None:
        """Менеджер не может изменять данные чужого кафе."""
        user = Mock(id=uuid.uuid4(), role=UserRole.MANAGER, cafe_id=uuid.uuid4())

        with self.assertRaises(PermissionDeniedError):
            ensure_manager_cafe_access(user, uuid.uuid4())

    def test_admin_can_access_any_cafe(self) -> None:
        """Администратор может работать с любым кафе."""
        user = Mock(id=uuid.uuid4(), role=UserRole.ADMIN, cafe_id=None)

        ensure_manager_cafe_access(user, uuid.uuid4())

    def test_manager_cannot_attach_dish_to_another_cafe(self) -> None:
        """Менеджер не может привязать блюдо к чужому кафе."""
        own_cafe_id = uuid.uuid4()
        user = Mock(id=uuid.uuid4(), role=UserRole.MANAGER, cafe_id=own_cafe_id)

        with self.assertRaises(PermissionDeniedError):
            ensure_manager_cafes_access(user, [own_cafe_id, uuid.uuid4()])


class ServiceLookupTests(IsolatedAsyncioTestCase):
    """Тесты поиска сущностей сервисным слоем."""

    async def test_get_cafe_raises_domain_error_when_missing(self) -> None:
        """Отсутствующее кафе приводит к доменной ошибке, а не HTTPException."""
        session = AsyncMock()
        cafe_reader = Mock(get=AsyncMock(return_value=None))

        with self.assertRaises(EntityNotFoundError):
            await get_cafe_or_raise(uuid.uuid4(), session, cafe_reader)

    async def test_manager_without_cafe_gets_empty_list(self) -> None:
        """Для менеджера без привязки возвращается пустой список."""
        user = Mock(id=uuid.uuid4(), role=UserRole.MANAGER, cafe_id=None)

        result = await get_manager_cafes(user, AsyncMock(), Mock())

        self.assertEqual(result, [])

    async def test_ensure_cafes_exist_reports_missing_cafe(self) -> None:
        """Проверка списка кафе сообщает о первом отсутствующем кафе."""
        first_id = uuid.uuid4()
        missing_id = uuid.uuid4()
        cafe_reader = Mock(get=AsyncMock(side_effect=[Mock(id=first_id), None]))

        with self.assertRaises(EntityNotFoundError) as raised:
            await ensure_cafes_exist(
                [first_id, missing_id],
                AsyncMock(),
                cafe_reader,
            )

        self.assertEqual(str(raised.exception), 'Кафе не найдено')

    async def test_slot_lookup_uses_single_resource_query(self) -> None:
        """Поиск слота не дублирует уже выполненную проверку кафе."""
        cafe_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        session = AsyncMock()
        slot_lookup = AsyncMock(return_value=None)

        with patch('services.slot.slot_crud.get_by_cafe_and_id', new=slot_lookup):
            with self.assertRaises(EntityNotFoundError):
                await get_slot_in_cafe_or_raise(
                    cafe_id,
                    slot_id,
                    session,
                )

        slot_lookup.assert_awaited_once_with(cafe_id, slot_id, session)
