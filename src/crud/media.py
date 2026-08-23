# src/crud/media.py
import asyncio
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.media import Media

# Папка на диске, куда сохраняются загруженные файлы
MEDIA_ROOT = Path('media')

# Максимальный допустимый размер файла (10 МБ).
# В старом методе размер вообще не проверялся во время чтения —
# файл сначала полностью загружался в память, и только потом
# можно было бы (но не проверялось) посмотреть его итоговый размер.
MAX_FILE_SIZE = 10 * 1024 * 1024

# Размер одного "чанка" (куска), которым будем читать файл.
# В отличие от старого метода, где файл читался одним вызовом
# upload.read() и целиком попадал в оперативную память,
# здесь мы читаем файл небольшими порциями по CHUNK_SIZE байт.
CHUNK_SIZE = 1024 * 1024


class MediaCRUD:
    """CRUD-операции для работы с медиафайлами."""

    def __init__(self, session: AsyncSession) -> None:
        """Инициализирует CRUD с сессией БД."""
        # Сохраняем сессию БД, чтобы использовать её во всех методах класса
        self.session = session

    async def save_file(self, upload: UploadFile) -> Media:
        """Сохраняет файл на диск и создаёт запись в БД.

        В отличие от старой версии метода, которая читала весь файл
        сразу (`content = await upload.read()`) и только потом писала
        его на диск одним куском, здесь файл читается и записывается
        небольшими частями (чанками) по мере поступления данных.
        Это позволяет не держать весь файл в памяти процесса и сразу
        прерывать загрузку, если файл оказался больше допустимого лимита.
        """
        # Создаём папку для файлов, если её ещё нет (в отдельном потоке)
        await asyncio.to_thread(MEDIA_ROOT.mkdir, parents=True, exist_ok=True)

        # Генерируем уникальный ID — он же станет частью имени файла на диске
        media_id = uuid.uuid4()
        # Берём расширение исходного файла (.jpg, .png и т.д.)
        extension = Path(upload.filename or '').suffix
        # Формируем новое безопасное имя файла на основе UUID
        filename = f'{media_id}{extension}'
        file_path = MEDIA_ROOT / filename

        # Счётчик фактически записанных байт.
        # В старом методе размер файла брался как len(content) уже
        # после того, как весь файл был прочитан в память —
        # здесь же размер считается постепенно, чанк за чанком.
        total_size = 0

        def _open_file():
            # Открываем файл на диске для побайтовой записи
            return open(file_path, 'wb')  # noqa: SIM115

        # Открытие файла — блокирующая операция, поэтому выполняем
        # её в отдельном потоке, как и запись/чтение ниже
        file_obj = await asyncio.to_thread(_open_file)
        try:
            # Читаем файл небольшими частями (чанками) в цикле.
            # Старый метод делал один await upload.read() без аргумента —
            # то есть требовал прочитать сразу ВЕСЬ файл целиком в память.
            # Здесь же upload.read(CHUNK_SIZE) читает максимум CHUNK_SIZE
            # байт за раз, поэтому в памяти одновременно находится только
            # один небольшой чанк, а не файл целиком.
            while chunk := await upload.read(CHUNK_SIZE):
                total_size += len(chunk)

                # Проверяем размер уже во время чтения, а не после.
                # В старом методе такой проверки не было вообще —
                # файл любого размера просто загружался целиком.
                if total_size > MAX_FILE_SIZE:
                    # Закрываем файл и удаляем недописанный кусок с диска,
                    # чтобы не оставлять "мусорные" файлы при превышении лимита
                    await asyncio.to_thread(file_obj.close)
                    await asyncio.to_thread(file_path.unlink, True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail='Файл превышает допустимый размер.',
                    )

                # Сразу дозаписываем прочитанный чанк на диск,
                # не дожидаясь, пока прочитается весь файл
                await asyncio.to_thread(file_obj.write, chunk)
        finally:
            # Файл обязательно закрываем, даже если было исключение
            await asyncio.to_thread(file_obj.close)

        # Создаём объект модели с метаданными файла для сохранения в БД.
        # size теперь берём из total_size, посчитанного по чанкам,
        # а не из len(content) для файла, загруженного целиком
        media = Media(
            id=media_id,
            filename=filename,
            content_type=upload.content_type or 'application/octet-stream',
            size=total_size,
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
