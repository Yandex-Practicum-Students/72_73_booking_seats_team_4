import asyncio
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.media import Media

# Папка на диске, куда сохраняются загруженные файлы
MEDIA_ROOT = Path('media')

# Максимальный допустимый размер файла (10 МБ)
MAX_FILE_SIZE = 10 * 1024 * 1024
# Размер одного "чанка" при чтении файла
CHUNK_SIZE = 1024 * 1024


class MediaCRUD:
    """CRUD-операции для работы с медиафайлами.

    Модель Media хранит только id. Сам файл лежит на диске под именем
    "{id}{расширение}", поэтому путь к файлу не хранится в БД отдельно —
    он всегда вычисляется из id.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Инициализирует CRUD с сессией БД."""
        self.session = session

    async def save_file(self, upload: UploadFile) -> Media:
        """Сохраняет файл на диск чанками и создаёт запись в БД."""
        await asyncio.to_thread(MEDIA_ROOT.mkdir, parents=True, exist_ok=True)

        # id генерируется на стороне Python, чтобы сразу знать имя файла на диске
        media_id = uuid.uuid4()
        extension = Path(upload.filename or '').suffix
        file_path = MEDIA_ROOT / f'{media_id}{extension}'

        total_size = 0

        def _open_file() -> object:
            return open(file_path, 'wb')  # noqa: SIM115

        file_obj = await asyncio.to_thread(_open_file)
        try:
            # Читаем файл небольшими частями, не загружая его целиком в память
            while chunk := await upload.read(CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    await asyncio.to_thread(file_obj.close)
                    await asyncio.to_thread(file_path.unlink, True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail='Файл превышает допустимый размер.',
                    )
                await asyncio.to_thread(file_obj.write, chunk)
        finally:
            await asyncio.to_thread(file_obj.close)

        # В модели хранится только id — путь к файлу не сохраняем в БД
        media = Media(id=media_id)
        self.session.add(media)
        await self.session.flush()
        await self.session.refresh(media)
        return media

    async def get_file_path(self, media_id: uuid.UUID) -> Path | None:
        """Возвращает путь к файлу на диске по ID, если запись существует."""
        # Проверяем, что запись с таким id есть в БД
        result = await self.session.execute(
            select(Media).where(Media.id == media_id),
        )
        media = result.scalar_one_or_none()
        if media is None:
            return None

        # Ищем файл на диске по маске "id.*", т.к. расширение не хранится в БД
        matches = list(MEDIA_ROOT.glob(f'{media_id}.*'))
        return matches[0] if matches else None
