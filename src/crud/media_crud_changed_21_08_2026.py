import asyncio
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.media import Media

# Папка на диске, куда сохраняются загруженные файлы
MEDIA_ROOT = Path('media')


class MediaCRUD:
    """CRUD-операции для работы с медиафайлами."""

    def __init__(self, session: AsyncSession) -> None:
        """Инициализирует CRUD с сессией БД."""
        # Сохраняем сессию БД, чтобы использовать её во всех методах класса
        self.session = session

    async def save_file(self, upload: UploadFile) -> Media:
        """Сохраняет файл на диск и создаёт запись в БД."""
        # Создаём папку для файлов, если её ещё нет (в отдельном потоке)
        await asyncio.to_thread(MEDIA_ROOT.mkdir, parents=True, exist_ok=True)

        # Генерируем уникальный ID — он же станет именем файла на диске
        media_id = uuid.uuid4()
        # Берём расширение исходного файла (.jpg, .png и т.д.)
        extension = Path(upload.filename or '').suffix
        # # Формируем новое безопасное имя файла на основе UUID  # УДАЛИТЬ
        # filename = f'{media_id}{extension}'  # УДАЛИТЬ
        file_path = MEDIA_ROOT / f'{media_id}{extension}'  # Добавлено — путь строим из media_id напрямую

        # Считываем содержимое загруженного файла в память
        content = await upload.read()
        # Записываем содержимое файла на диск (в отдельном потоке)
        await asyncio.to_thread(file_path.write_bytes, content)

        # Создаём объект модели с метаданными файла для сохранения в БД
        media = Media(
            id=media_id,
            # filename=filename,  # УДАЛИТЬ
            content_type=upload.content_type or 'application/octet-stream',
            size=len(content),
            file_path=str(file_path),
            original_name=upload.filename,
        )
        # Добавляем объект в сессию (пока не сохранён окончательно)
        self.session.add(media)
        # Отправляем изменения в БД (получаем ID и другие значения по умолчанию)
        await self.session.flush()
        # Обновляем объект данными из БД (created_at, updated_at и т.д.)
        await self.session.refresh(media)
        return media

    async def get_by_id(self, media_id: uuid.UUID) -> Media | None:
        """Возвращает медиафайл по ID, если он активен (не удалён)."""
        # Ищем запись в БД по ID, исключая "удалённые" (is_active=False)
        result = await self.session.execute(
            select(Media).where(Media.id == media_id, Media.is_active.is_(True)),
        )
        # Возвращаем найденный объект или None, если ничего не нашлось
        return result.scalar_one_or_none()

# Удалить: строки 32, 33, 44
# Добавлено: строка 34
