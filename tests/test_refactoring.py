import ast
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from exceptions.common import PermissionDeniedError
from main import app
from models.user import UserRole
from schemas.action import ActionCreate
from schemas.cafe import CafeCreate
from schemas.dish import DishCreate, DishUpdate
from services.action import create_action
from services.cafe import create_cafe
from services.dish import create_dish, update_dish

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LayeringTests(TestCase):
    """Фиксирует границы между CRUD, сервисами и HTTP-слоем."""

    def test_crud_does_not_import_services(self) -> None:
        """CRUD остаётся слоем хранения и не вызывает бизнес-сервисы."""
        for source_path in (PROJECT_ROOT / 'src' / 'crud').glob('*.py'):
            tree = ast.parse(source_path.read_text(encoding='utf-8-sig'))
            service_imports = []
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and node.module.startswith('services')
                ):
                    service_imports.append(node.module)
                elif isinstance(node, ast.Import):
                    service_imports.extend(
                        alias.name for alias in node.names if alias.name.startswith('services')
                    )
            self.assertEqual(service_imports, [], source_path.name)

    def test_response_metadata_is_kept_out_of_endpoints(self) -> None:
        """Наборы HTTP-статусов объявлены в пакете api.responses."""
        for source_path in (PROJECT_ROOT / 'src' / 'api' / 'endpoints').glob('*.py'):
            tree = ast.parse(source_path.read_text(encoding='utf-8'))
            response_assignments = [
                target.id
                for node in tree.body
                if isinstance(node, (ast.Assign, ast.AnnAssign))
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                if isinstance(target, ast.Name) and target.id.endswith('_RESPONSES')
            ]
            self.assertEqual(response_assignments, [], source_path.name)

            inline_statuses = []
            for function in (
                node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ):
                for decorator in function.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue
                    for keyword in decorator.keywords:
                        if keyword.arg not in {'responses', 'status_code'}:
                            continue
                        inline_statuses.extend(
                            child.attr
                            for child in ast.walk(keyword.value)
                            if isinstance(child, ast.Attribute)
                            and isinstance(child.value, ast.Name)
                            and child.value.id == 'status'
                        )
            self.assertEqual(inline_statuses, [], source_path.name)

        action_responses = app.openapi()['paths']['/api/v1/actions']['post']['responses']
        self.assertEqual(set(action_responses), {'201', '400', '401', '403', '422'})


class ServiceWorkflowTests(IsolatedAsyncioTestCase):
    """Проверяет перенесённые из ручек и CRUD сценарии."""

    async def test_action_service_checks_relations_before_create(self) -> None:
        """Создание акции валидирует кафе до записи."""
        cafe_id = uuid.uuid4()
        payload = ActionCreate(
            description='Скидка на завтрак',
            photo_id=None,
            cafes_id=[cafe_id],
        )
        admin = SimpleNamespace(id=uuid.uuid4(), role=UserRole.ADMIN, cafe_id=None)
        session = AsyncMock()
        redis = AsyncMock()
        ensure_cafes = AsyncMock()
        create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

        with (
            patch('services.action.ensure_cafes_exist', new=ensure_cafes),
            patch('services.action.action_crud.create', new=create),
        ):
            result = await create_action(payload, admin, session, redis)

        ensure_cafes.assert_awaited_once_with([cafe_id], session)
        create.assert_awaited_once_with(payload, session, redis)
        self.assertIs(result, create.return_value)

    async def test_dish_service_checks_media_before_create(self) -> None:
        """Проверка изображения выполняется сервисом, а не CRUD."""
        cafe_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        payload = DishCreate(
            name='Борщ',
            price='250.00',
            photo_id=photo_id,
            cafes_id=[cafe_id],
        )
        admin = SimpleNamespace(id=uuid.uuid4(), role=UserRole.ADMIN, cafe_id=None)
        session = AsyncMock()
        redis = AsyncMock()
        ensure_cafes = AsyncMock()
        get_media = AsyncMock()
        create = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

        with (
            patch('services.dish.ensure_cafes_exist', new=ensure_cafes),
            patch('services.dish.get_media_or_raise', new=get_media),
            patch('services.dish.dish_crud.create', new=create),
        ):
            result = await create_dish(payload, admin, session, redis)

        ensure_cafes.assert_awaited_once_with([cafe_id], session)
        get_media.assert_awaited_once_with(photo_id, session, check_file=False)
        create.assert_awaited_once_with(payload, session, redis)
        self.assertIs(result, create.return_value)

    async def test_dish_update_rejects_foreign_current_cafe(self) -> None:
        """Менеджер не может перепривязать чужое блюдо к своему кафе."""
        own_cafe_id = uuid.uuid4()
        dish = SimpleNamespace(
            id=uuid.uuid4(),
            cafes=[SimpleNamespace(id=uuid.uuid4())],
        )
        payload = DishUpdate(cafes_id=[own_cafe_id])
        manager = SimpleNamespace(
            id=uuid.uuid4(),
            role=UserRole.MANAGER,
            cafe_id=own_cafe_id,
        )
        update = AsyncMock()

        with patch('services.dish.dish_crud.update', new=update):
            with self.assertRaises(PermissionDeniedError):
                await update_dish(
                    dish,
                    payload,
                    manager,
                    AsyncMock(),
                    AsyncMock(),
                )

        update.assert_not_awaited()

    async def test_cafe_service_owns_manager_validation_and_sync(self) -> None:
        """Создание кафе проверяет и синхронизирует менеджеров в сервисе."""
        manager_id = uuid.uuid4()
        payload = CafeCreate(
            name='Кафе',
            address='Адрес',
            phone='+79991234567',
            managers_id=[manager_id],
        )
        session = AsyncMock()
        redis = AsyncMock()
        cafe = SimpleNamespace(id=uuid.uuid4(), name=payload.name, managers=[])
        ensure_managers = AsyncMock()
        create = AsyncMock(return_value=SimpleNamespace(id=cafe.id))
        get_cafe = AsyncMock(return_value=cafe)
        sync_managers = AsyncMock()

        with (
            patch('services.cafe.ensure_managers_exist_and_role', new=ensure_managers),
            patch('services.cafe.cafe_crud.create', new=create),
            patch('services.cafe.cafe_crud.get', new=get_cafe),
            patch('services.cafe.sync_managers', new=sync_managers),
        ):
            result = await create_cafe(payload, session, redis)

        ensure_managers.assert_awaited_once_with([manager_id], session)
        create.assert_awaited_once_with(payload, session, redis)
        get_cafe.assert_awaited_once_with(cafe.id, session)
        sync_managers.assert_awaited_once_with(cafe, [manager_id], session)
        session.flush.assert_awaited_once()
        self.assertIs(result, cafe)
