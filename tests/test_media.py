import os
import sys
import uuid
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException, UploadFile

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


class MediaCRUDTests(IsolatedAsyncioTestCase):
    """Проверяет загрузку и поиск медиафайлов."""

    async def test_save_file_creates_record_and_writes_to_disk(self) -> None:
        """save_file сохраняет файл на диск чанками и создаёт запись в БД."""
        session = AsyncMock()
        crud = MediaCRUD(session)
        upload = _make_upload(b'test image content')

        media = await crud.save_file(upload)

        self.assertIsInstance(media, Media)
        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(media)

        saved_files = list(media_module.MEDIA_ROOT.glob(f'{media.id}.*'))
        self.assertEqual(len(saved_files), 1)
        self.assertEqual(saved_files[0].read_bytes(), b'test image content')
        saved_files[0].unlink()

    async def test_save_file_rejects_files_over_size_limit(self) -> None:
        """save_file прерывает загрузку и удаляет файл при превышении лимита."""
        session = AsyncMock()
        crud = MediaCRUD(session)
        oversized_content = b'x' * (media_module.MAX_FILE_SIZE + media_module.CHUNK_SIZE)
        upload = _make_upload(oversized_content)

        with self.assertRaises(HTTPException) as raised:
            await crud.save_file(upload)

        self.assertEqual(raised.exception.status_code, 413)
        session.add.assert_not_called()

    async def test_get_file_path_returns_none_for_unknown_id(self) -> None:
        """get_file_path возвращает None, если записи с таким id нет в БД."""
        session = AsyncMock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        crud = MediaCRUD(session)

        result = await crud.get_file_path(uuid.uuid4())

        self.assertIsNone(result)
