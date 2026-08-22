# src/api/endpoints/media.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import StaffUser
from crud.media import MediaCRUD
from schemas.media import MediaInfo

from core.db import get_session

router = APIRouter()


@router.post(
    '',
    response_model=MediaInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Загрузка изображения',
)
async def upload_media(
    file: UploadFile,
    _: StaffUser,
    session: AsyncSession = Depends(get_session),
) -> MediaInfo:
    """Загружает изображение и сохраняет его метаданные в БД."""
    crud = MediaCRUD(session)
    media = await crud.save_file(file)
    return MediaInfo(media_id=media.id)


@router.get(
    '/{media_id}',
    summary='Получение изображения по ID',
)
async def get_media(
    media_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Возвращает файл изображения по его ID."""
    crud = MediaCRUD(session)
    media = await crud.get_by_id(media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Изображение не найдено.',
        )
    return FileResponse(media.file_path, media_type=media.content_type)
