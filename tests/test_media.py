import os
import sys
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import crud.media as media_module  # noqa: E402
from crud.media import MediaCRUD  # noqa: E402
from models.media import Media  # noqa: E402


def _make_upload(content: bytes, filename: str = 'photo.jpg') -> Mock:
    """Создаёт мок UploadFile, эмулирующий чтение файла чанками."""
    remaining = [content]

    async def _read(size: int = -1) -> bytes:
        if not remaining[0]:
            return b''
        chunk, remaining[0] = remaining[0][:size], remaining[0][size:]
        return chunk

    upload = Mock(spec=UploadFile)
    upload.filename = filename
    upload.content_type = 'image/jpeg'
    upload.read = AsyncMock(side_effect=_read)
    return upload


def _make_session() -> Mock:
    """Создаёт мок сессии БД с реальной сигнатурой AsyncSession.

    add() — синхронный метод, flush()/refresh()/execute() — асинхронные.
    Используем spec, чтобы синхронный метод не подменялся AsyncMock.
    """
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


def _execute_result_for(media_id: uuid.UUID) -> Mock:
    """Создаёт синхронный результат execute() с готовым media_id."""
    result = Mock()
    result.scalar_one_or_none = Mock(return_value=Mock(id=media_id))
    return result


class MediaCRUDTests(IsolatedAsyncioTestCase):
    """Проверяет загрузку и поиск медиафайлов."""

    def setUp(self) -> None:
        """Подменяет MEDIA_ROOT на временную папку на время теста."""
        self._tmp_dir = TemporaryDirectory()
        self._original_media_root = media_module.MEDIA_ROOT
        media_module.MEDIA_ROOT = Path(self._tmp_dir.name)
        self.addCleanup(self._tmp_dir.cleanup)
        self.addCleanup(setattr, media_module, 'MEDIA_ROOT', self._original_media_root)

    async def test_save_file_creates_record_and_writes_to_disk(self) -> None:
        """save_file сохраняет файл на диск чанками и создаёт запись в БД."""
        session = _make_session()
        crud = MediaCRUD(session)
        upload = _make_upload(b'test image content')

        media = await crud.save_file(upload)

        self.assertIsInstance(media, Media)
        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(media)

        saved_files = list(media_module.MEDIA_ROOT.glob(f'{media.id}*'))
        self.assertEqual(len(saved_files), 1)
        self.assertEqual(saved_files[0].read_bytes(), b'test image content')

    async def test_save_file_without_extension(self) -> None:
        """save_file корректно сохраняет файл без расширения."""
        session = _make_session()
        crud = MediaCRUD(session)
        upload = _make_upload(b'raw content', filename='noext')

        media = await crud.save_file(upload)

        saved_files = list(media_module.MEDIA_ROOT.glob(f'{media.id}*'))
        self.assertEqual(len(saved_files), 1)
        self.assertEqual(saved_files[0].name, str(media.id))

    async def test_save_file_rejects_files_over_size_limit(self) -> None:
        """save_file прерывает загрузку и удаляет файл при превышении лимита."""
        session = _make_session()
        crud = MediaCRUD(session)
        oversized_content = b'x' * (media_module.MAX_FILE_SIZE + media_module.CHUNK_SIZE)
        upload = _make_upload(oversized_content)

        with self.assertRaises(HTTPException) as raised:
            await crud.save_file(upload)

        self.assertEqual(raised.exception.status_code, 413)
        session.add.assert_not_called()

    async def test_get_file_path_returns_none_for_unknown_id(self) -> None:
        """get_file_path возвращает None, если записи с таким id нет в БД."""
        session = _make_session()
        execute_result = Mock()
        execute_result.scalar_one_or_none = Mock(return_value=None)
        session.execute.return_value = execute_result
        crud = MediaCRUD(session)

        result = await crud.get_file_path(uuid.uuid4())

        self.assertIsNone(result)

    async def test_get_file_path_returns_path_for_existing_file(self) -> None:
        """get_file_path возвращает путь к файлу, если запись и файл существуют."""
        session = _make_session()
        crud = MediaCRUD(session)
        upload = _make_upload(b'existing image content')
        media = await crud.save_file(upload)

        session.execute.return_value = _execute_result_for(media.id)

        result = await crud.get_file_path(media.id)

        self.assertIsNotNone(result)
        self.assertTrue(result.name.startswith(str(media.id)))
        self.assertEqual(result.read_bytes(), b'existing image content')
