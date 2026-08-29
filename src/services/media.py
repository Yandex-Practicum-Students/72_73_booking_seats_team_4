import uuid
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.media import MediaCRUD
from services.errors import EntityNotFoundError


async def get_media_or_raise(
        media_id: uuid.UUID,
        session: AsyncSession,
        check_file: bool = True,
) -> Path:
    """Возвращает путь к файлу медиа или выбрасывает ошибку."""
    logger.info('Проверка существования медиа: media_id={}', media_id)

    media_crud = MediaCRUD(session)

    file_path = await media_crud.get_file_path(media_id)

    if file_path is None:
        logger.warning('Медиа не найдено: media_id={}', media_id)
        raise EntityNotFoundError(f'Изображение с ID "{media_id}" не найдено')
    logger.info('Медиа найдено: media_id={}, path={}', media_id, file_path)
    return file_path
