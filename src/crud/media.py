import asyncio
import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.media import Media

MEDIA_ROOT = Path('media')

# Лимит согласован с командой: 5 МБ (было 10 МБ)
MAX_FILE_SIZE = 5 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

# Разрешённые форматы изображений на входе
ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png'}
JPEG_QUALITY = 90


class MediaCRUD:
    """CRUD-операции для работы с медиафайлами."""

    def __init__(self, session: AsyncSession) -> None:
        """Инициализирует CRUD с сессией БД."""
        self.session = session

    async def save_file(self, upload: UploadFile) -> Media:
        """Сохраняет файл на диск чанками, конвертирует в JPG и создаёт запись в БД."""
        await asyncio.to_thread(MEDIA_ROOT.mkdir, parents=True, exist_ok=True)

        # Проверяем content-type ещё до чтения тела файла
        if upload.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail='Разрешены только форматы JPG и PNG.',
            )

        # Читаем файл чанками в память (но не больше лимита), не пишем сразу на диск —
        # финальный файл всегда JPG, поэтому промежуточный формат нам не нужен
        buffer = io.BytesIO()
        total_size = 0
        while chunk := await upload.read(CHUNK_SIZE):
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail='Файл превышает допустимый размер.',
                )
            buffer.write(chunk)

        buffer.seek(0)

        def _convert_to_jpeg() -> bytes:
            """Открывает изображение и конвертирует его в JPEG (в отдельном потоке)."""
            try:
                image = Image.open(buffer)
                image.load()
            except UnidentifiedImageError:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail='Файл не является корректным изображением JPG или PNG.',
                )
            if image.mode in ('RGBA', 'P', 'LA'):
                image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=JPEG_QUALITY)
            return output.getvalue()

        jpeg_bytes = await asyncio.to_thread(_convert_to_jpeg)

        media_id = uuid.uuid4()
        file_path = MEDIA_ROOT / f'{media_id}.jpg'

        try:
            await asyncio.to_thread(file_path.write_bytes, jpeg_bytes)
        except OSError:
            await asyncio.to_thread(file_path.unlink, True)
            raise

        media = Media(id=media_id, name=upload.filename or f'{media_id}.jpg')
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
            lambda: list(MEDIA_ROOT.glob(f'{media_id}*')),
        )
        return matches[0] if matches else None
