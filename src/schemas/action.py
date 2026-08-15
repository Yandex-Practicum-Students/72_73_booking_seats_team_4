import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ActionCreate(BaseModel):
    """Схема создания акции."""

    model_config = ConfigDict(extra='forbid')

    description: str = Field(..., min_length=1)
    photo_id: Optional[uuid.UUID] = Field(None)
    cafes_id: list[uuid.UUID] = Field(default_factory=list)


class ActionShortInfo(BaseModel):
    """Краткая информация об акции."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    photo_id: Optional[uuid.UUID]


class ActionInfo(ActionShortInfo):
    """Схема полных данных об акции."""

    is_active: bool
    # В FullBaseSchemaDB Андрея поле называется create_date,
    # в OpenAPI и здесь - created_at.
    # Нужно уточнить какой имя оставим.
    created_at: datetime
    updated_at: datetime


class ActionUpdate(BaseModel):
    """Схема редактирования акции."""

    model_config = ConfigDict(extra='forbid')

    description: Optional[str] = Field(None, min_length=1)
    photo_id: Optional[uuid.UUID] = Field(None)
    cafes_id: Optional[list[uuid.UUID]] = Field(None)
    is_active: Optional[bool] = Field(None)
