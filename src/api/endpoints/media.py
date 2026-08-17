# scr/api/endpoints/media.py

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import StaffUser
from crud.media import MediaCRUD
from schemas.media import MediaInfo


from core.db import get_session

#  Роутер для работы с изображеними (  загрузка и получение по ID)
media_router = APIRouter(prefix='/media', tags=['Изображения'])


@media_router.post(
    '',
    response_model=MediaInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Загрузка изображения',
)
async def upload_media(
    file: UploadFile,
    user: StaffUser,  # достуб только администраторам и менеджерам
    session: AsyncSession = Depends(get_session),
) -> MediaInfo:
    """Загружает изображение и сохраняет его метаданные в БД."""
    # Создаём CRUD-объект для работы с медиафайлами
    crud = MediaCRUD(session)
    # Сохраняем файл на диск и создаём запись в базе данных
    media = await crud.save_file(file)
    # Возвращаем клиенту только ID созданного изображения
    return MediaInfo(media_id=media.id)



@media_router.get(
    '/{media_id}',
    summary='Получение изображения по ID',
)
async def get_media(
    media_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Возвращает файл изображения по его ID."""
    crud = MediaCRUD(session)
    # Ищем запись об изображении в базе данных
    media = await crud.get_by_id(media_id)
    # Если изображение не найдено или неактивно —   возвращаем 404
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Изображение не найдено.',
        )
    # Отдаём сам файл клиенту (браузер отобразит картинку по прямой сылке)
    return FileResponse(media.file_path, media_type=media.content_type)
