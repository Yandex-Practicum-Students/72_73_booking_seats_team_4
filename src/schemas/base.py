from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

import constants


class BaseInfoScheme(BaseModel):
    """Схема общих полей для всех подробных инфо-схем."""

    is_active: bool
    created_at: datetime
    updated_at: datetime


class DescriptionScheme(BaseModel):
    """Добавляет поле description."""

    description: Optional[str] = Field(None, min_length=constants.DESCRIPTION_MIN_LNGH)
