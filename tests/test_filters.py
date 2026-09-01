from types import SimpleNamespace
from unittest import TestCase

from api.dependencies.filters import resolve_show_active
from models.user import UserRole


class ShowActiveFilterTests(TestCase):
    """Проверяет единые правила фильтра активности."""

    def test_admin_keeps_requested_value(self) -> None:
        """Администратор может выбрать True, False или None."""
        admin = SimpleNamespace(role=UserRole.ADMIN)

        self.assertIsNone(resolve_show_active(admin, None))
        self.assertIs(resolve_show_active(admin, False), False)

    def test_user_is_limited_to_active_resources(self) -> None:
        """Пользователь не может запросить неактивные ресурсы."""
        user = SimpleNamespace(role=UserRole.USER)

        self.assertIs(resolve_show_active(user, False), True)

    def test_manager_filter_can_be_enabled_per_resource(self) -> None:
        """Для управляемого ресурса менеджеру доступен явный фильтр."""
        manager = SimpleNamespace(role=UserRole.MANAGER)

        self.assertIs(resolve_show_active(manager, False, manager_can_filter=True), False)
        self.assertIs(resolve_show_active(manager, None, manager_can_filter=True), True)

    def test_manager_is_limited_when_filter_is_not_enabled(self) -> None:
        """Без разрешения менеджер получает только активные ресурсы."""
        manager = SimpleNamespace(role=UserRole.MANAGER)

        self.assertIs(resolve_show_active(manager, False), True)
