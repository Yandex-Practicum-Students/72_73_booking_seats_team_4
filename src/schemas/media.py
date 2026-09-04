import uuid

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict


class MediaData(BaseModel):
    """Данные загрузки изображения (по OpenAPI)."""

    file: UploadFile


class MediaInfo(BaseModel):
    """Ответ при загрузке изображения (по OpenAPI)."""

    media_id: uuid.UUID


class MediaDB(BaseModel):
    """Внутренняя схема записи о медиафайле (не для API).

    Используется для работы с базой данных.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
