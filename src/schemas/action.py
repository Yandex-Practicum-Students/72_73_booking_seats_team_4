import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.base import BaseInfoScheme, IdScheme
from schemas.cafe import CafeShortInfo
from schemas.validators import field_cannot_be_null, validate_empty_field

from core.constants import ACTION_DESCRIPTION_MAX_LENGTH


class ActionBase(BaseModel):
    """Общие поля акции."""

    model_config = ConfigDict(extra='forbid')

    description: str = Field(..., max_length=ACTION_DESCRIPTION_MAX_LENGTH)
    photo_id: Optional[uuid.UUID]


class ActionCreate(ActionBase):
    """Схема создания акции."""

    cafes_id: list[uuid.UUID]

    check_not_empty_fields = field_validator('description', 'cafes_id')(validate_empty_field)


class ActionInfo(IdScheme, ActionBase, BaseInfoScheme):
    """Схема полных данных об акции."""

    cafes: list[CafeShortInfo]


class ActionUpdate(ActionCreate):
    """Схема редактирования акции."""

    description: Optional[str] = Field(None, max_length=ACTION_DESCRIPTION_MAX_LENGTH)
    photo_id: Optional[uuid.UUID] = Field(None)
    cafes_id: Optional[list[uuid.UUID]] = Field(None)
    is_active: Optional[bool] = Field(None)

    check_not_null_fields = field_validator('description', 'cafes_id')(field_cannot_be_null)
