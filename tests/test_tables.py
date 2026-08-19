import uuid
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, status

from api.dependencies.tables import get_cafe_or_404, get_table_in_cafe, get_table_or_404


class TablesTests(IsolatedAsyncioTestCase):
    """Тесты для столов."""

    @pytest.mark.asyncio
    async def test_get_cafe_or_404_raises_if_cafe_not_found(self) -> None:
        """get_cafe_or_404 выбрасывает 404, если кафе не найдено."""
        session = AsyncMock()

        with patch('api.dependencies.tables.cafe_crud.get', new=AsyncMock(return_value=None)):
            with self.assertRaises(HTTPException) as raised:
                await get_cafe_or_404(uuid.uuid4(), session)

            self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(raised.exception.detail, 'Кафе не найдено')

    @pytest.mark.asyncio
    async def test_get_cafe_or_404_returns_cafe_if_exists(self) -> None:
        """get_cafe_or_404 возвращает кафе, если оно существует."""
        cafe_id = uuid.uuid4()
        session = AsyncMock()
        mock_cafe = Mock()
        mock_cafe.id = cafe_id

        with patch('api.dependencies.tables.cafe_crud.get', new=AsyncMock(return_value=mock_cafe)):
            result = await get_cafe_or_404(cafe_id, session)
            self.assertEqual(result, mock_cafe)

    @pytest.mark.asyncio
    async def test_get_table_or_404_raises_if_table_not_found(self) -> None:
        """get_table_or_404 выбрасывает 404, если стол не найден."""
        session = AsyncMock()

        with patch('api.dependencies.tables.table_crud.get', new=AsyncMock(return_value=None)):
            with self.assertRaises(HTTPException) as raised:
                await get_table_or_404(uuid.uuid4(), session)

            self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(raised.exception.detail, 'Стол не найден')

    @pytest.mark.asyncio
    async def test_get_table_or_404_returns_table_if_exists(self) -> None:
        """get_table_or_404 возвращает стол, если он существует."""
        table_id = uuid.uuid4()
        session = AsyncMock()
        mock_table = Mock()
        mock_table.id = table_id

        with patch('api.dependencies.tables.table_crud.get', new=AsyncMock(return_value=mock_table)):
            result = await get_table_or_404(table_id, session)
            self.assertEqual(result, mock_table)

    @pytest.mark.asyncio
    async def test_get_table_in_cafe_raises_if_table_belongs_to_other_cafe(self) -> None:
        """get_table_in_cafe выбрасывает 404, если стол не принадлежит кафе."""
        cafe_id = uuid.uuid4()
        table_id = uuid.uuid4()
        session = AsyncMock()

        mock_cafe = Mock()
        mock_cafe.id = cafe_id

        mock_table = Mock()
        mock_table.id = table_id
        mock_table.cafe_id = uuid.uuid4()

        with patch('api.dependencies.tables.get_cafe_or_404', new=AsyncMock(return_value=mock_cafe)):
            with patch('api.dependencies.tables.get_table_or_404', new=AsyncMock(return_value=mock_table)):
                with self.assertRaises(HTTPException) as raised:
                    await get_table_in_cafe(cafe_id, table_id, session)

                self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(raised.exception.detail, 'Стол не найден в этом кафе')

    @pytest.mark.asyncio
    async def test_get_table_in_cafe_returns_table_if_belongs_to_cafe(self) -> None:
        """get_table_in_cafe возвращает стол, принадлежащий кафе."""
        cafe_id = uuid.uuid4()
        table_id = uuid.uuid4()
        session = AsyncMock()

        mock_cafe = Mock()
        mock_cafe.id = cafe_id

        mock_table = Mock()
        mock_table.id = table_id
        mock_table.cafe_id = cafe_id

        with patch('api.dependencies.tables.get_cafe_or_404', new=AsyncMock(return_value=mock_cafe)):
            with patch('api.dependencies.tables.get_table_or_404', new=AsyncMock(return_value=mock_table)):
                result = await get_table_in_cafe(cafe_id, table_id, session)
                self.assertEqual(result, mock_table)
