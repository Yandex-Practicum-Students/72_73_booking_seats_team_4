import os
import sys
import uuid
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException, status

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from api.dependencies.tables import get_cafe_or_404, get_table_in_cafe  # noqa: E402


class TablesTests(IsolatedAsyncioTestCase):
    """Тесты для столов."""

    async def test_get_cafe_or_404_raises_if_cafe_not_found(self) -> None:
        """get_cafe_or_404 выбрасывает 404, если кафе не найдено."""
        session = AsyncMock()

        with patch('api.dependencies.tables.cafe_crud.get', new=AsyncMock(return_value=None)):
            with self.assertRaises(HTTPException) as raised:
                await get_cafe_or_404(uuid.uuid4(), session)

            self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(raised.exception.detail, 'Кафе не найдено')

    async def test_get_cafe_or_404_returns_cafe_if_exists(self) -> None:
        """get_cafe_or_404 возвращает кафе, если оно существует."""
        cafe_id = uuid.uuid4()
        session = AsyncMock()
        mock_cafe = Mock()
        mock_cafe.id = cafe_id

        with patch('api.dependencies.tables.cafe_crud.get', new=AsyncMock(return_value=mock_cafe)):
            result = await get_cafe_or_404(cafe_id, session)
            self.assertEqual(result, mock_cafe)

    async def test_get_table_in_cafe_raises_if_table_not_found(self) -> None:
        """get_table_in_cafe выбрасывает 404 для чужого или отсутствующего стола."""
        cafe_id = uuid.uuid4()
        table_id = uuid.uuid4()
        session = AsyncMock()
        get_by_cafe_and_id = AsyncMock(return_value=None)

        with patch(
            'api.dependencies.tables.table_crud.get_by_cafe_and_id',
            new=get_by_cafe_and_id,
        ):
            with self.assertRaises(HTTPException) as raised:
                await get_table_in_cafe(cafe_id, table_id, session)

        get_by_cafe_and_id.assert_awaited_once_with(cafe_id, table_id, session)
        self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(raised.exception.detail, 'Стол не найден в этом кафе')

    async def test_get_table_in_cafe_returns_table_if_belongs_to_cafe(self) -> None:
        """get_table_in_cafe возвращает стол, принадлежащий кафе."""
        cafe_id = uuid.uuid4()
        table_id = uuid.uuid4()
        session = AsyncMock()

        mock_table = Mock()
        mock_table.id = table_id
        mock_table.cafe_id = cafe_id
        get_by_cafe_and_id = AsyncMock(return_value=mock_table)

        with patch(
            'api.dependencies.tables.table_crud.get_by_cafe_and_id',
            new=get_by_cafe_and_id,
        ):
            result = await get_table_in_cafe(cafe_id, table_id, session)

        get_by_cafe_and_id.assert_awaited_once_with(cafe_id, table_id, session)
        self.assertEqual(result, mock_table)
