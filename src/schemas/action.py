import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.base import BaseInfoScheme, IdScheme

from core.constants import ACTION_DESCRIPTION_MAX_LENGTH


class ActionCreate(BaseModel):
    """Схема создания акции."""

    model_config = ConfigDict(extra='forbid')

    description: str = Field(..., max_length=ACTION_DESCRIPTION_MAX_LENGTH)
    photo_id: Optional[uuid.UUID]
    cafes_id: list[uuid.UUID] = Field(default_factory=list)


class ActionInfo(IdScheme, ActionCreate, BaseInfoScheme):
    """Схема полных данных об акции."""


class ActionUpdate(BaseModel):
    """Схема редактирования акции."""

    model_config = ConfigDict(extra='forbid')

    description: Optional[str] = Field(None, max_length=ACTION_DESCRIPTION_MAX_LENGTH)
    photo_id: Optional[uuid.UUID] = Field(None)
    cafes_id: Optional[list[uuid.UUID]] = Field(None)
    is_active: Optional[bool] = Field(None)
