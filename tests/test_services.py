import os
import sys
import uuid
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from models.user import UserRole  # noqa: E402
from services.cafe import (  # noqa: E402
    ensure_manager_cafe_access,
    get_cafe_or_raise,
    get_manager_cafes,
)
from services.dish import (  # noqa: E402
    ensure_cafes_exist,
)
from services.dish import (
    ensure_manager_cafe_access as ensure_dish_manager_access,
)
from services.errors import EntityNotFoundError, PermissionDeniedError  # noqa: E402
from services.slot import get_slot_in_cafe_or_raise  # noqa: E402


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
            ensure_dish_manager_access(user, [own_cafe_id, uuid.uuid4()])


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
        get_cafe = AsyncMock(side_effect=[Mock(id=first_id), None])

        with patch('services.dish.cafe_crud.get', new=get_cafe):
            with self.assertRaises(EntityNotFoundError) as raised:
                await ensure_cafes_exist([first_id, missing_id], AsyncMock())

        self.assertEqual(str(raised.exception), 'Кафе не найдено')

    async def test_slot_lookup_checks_cafe_before_slot(self) -> None:
        """Поиск слота сначала проверяет существование родительского кафе."""
        cafe_id = uuid.uuid4()
        slot_id = uuid.uuid4()
        session = AsyncMock()
        cafe_reader = Mock()
        cafe_check = AsyncMock(side_effect=EntityNotFoundError('Кафе не найдено'))
        slot_lookup = AsyncMock()

        with (
            patch('services.slot.get_cafe_or_raise', new=cafe_check),
            patch('services.slot.slot_crud.get_by_cafe_and_id', new=slot_lookup),
        ):
            with self.assertRaises(EntityNotFoundError):
                await get_slot_in_cafe_or_raise(
                    cafe_id,
                    slot_id,
                    session,
                    cafe_reader,
                )

        cafe_check.assert_awaited_once_with(cafe_id, session, cafe_reader)
        slot_lookup.assert_not_awaited()
