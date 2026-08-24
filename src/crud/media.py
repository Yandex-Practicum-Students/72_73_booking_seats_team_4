import asyncio
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.media import Media

MEDIA_ROOT = Path('media')

MAX_FILE_SIZE = 10 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


class MediaCRUD:
    """CRUD-операции для работы с медиафайлами."""

    def __init__(self, session: AsyncSession) -> None:
        """Инициализирует CRUD с сессией БД."""
        self.session = session

    async def save_file(self, upload: UploadFile) -> Media:
        """Сохраняет файл на диск чанками и создаёт запись в БД."""
        await asyncio.to_thread(MEDIA_ROOT.mkdir, parents=True, exist_ok=True)
        media_id = uuid.uuid4()
        extension = Path(upload.filename or '').suffix
        file_path = MEDIA_ROOT / f'{media_id}{extension}'
        total_size = 0

        def _open_file() -> object:
            return open(file_path, 'wb')

        file_obj = await asyncio.to_thread(_open_file)
        try:
            while chunk := await upload.read(CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    await asyncio.to_thread(file_obj.close)
                    await asyncio.to_thread(file_path.unlink, True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail='File too large.',
                    )
                await asyncio.to_thread(file_obj.write, chunk)
        finally:
            await asyncio.to_thread(file_obj.close)

        media = Media(id=media_id)
        self.session.add(media)
        await self.session.flush()
        await self.session.refresh(media)
        return media

    async def get_file_path(self, media_id: uuid.UUID) -> Path | None:
        """Возвращает путь к файлу на диске по ID, если запись существует."""
        result = await self.session.execute(
            select(Media).where(Media.id == media_id),
        )
        media = result.scalar_one_or_none()
        if media is None:
            return None

        matches = await asyncio.to_thread(
            lambda: list(MEDIA_ROOT.glob(f'{media_id}.*')),
        )
        return matches[0] if matches else None
