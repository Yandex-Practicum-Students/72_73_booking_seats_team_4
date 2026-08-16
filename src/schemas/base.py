import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from core.constants import COMMON_DESCRIPTION_MAX_LENGTH


class BaseInfoScheme(BaseModel):
    """Схема общих полей для всех подробных инфо-схем."""

    is_active: bool
    created_at: datetime
    updated_at: datetime


class IdScheme(BaseModel):
    """Добавляет поле id."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class DescriptionScheme(BaseModel):
    """Добавляет поле description."""

    description: Optional[str] = Field(None, max_length=COMMON_DESCRIPTION_MAX_LENGTH)
