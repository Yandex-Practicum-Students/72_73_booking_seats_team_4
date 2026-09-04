import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from api.dependencies.permissions import StaffUser
from api.responses.statuses import CREATED
from crud.media import MediaCRUD
from schemas.media import MediaInfo

from core.db import DBSession

router = APIRouter()


@router.post(
    '',
    response_model=MediaInfo,
    status_code=CREATED,
    summary='Загрузка изображения',
)
async def upload_media(
    file: UploadFile,
    _: StaffUser,
    session: DBSession,
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
    session: DBSession,
) -> FileResponse:
    """Возвращает файл изображения по его ID."""
    crud = MediaCRUD(session)
    file_path = await crud.get_file_path(media_id)
    if file_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Изображение не найдено.',
        )
    return FileResponse(file_path)
