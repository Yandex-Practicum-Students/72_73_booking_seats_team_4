import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DishCreate(BaseModel):
    """Схема создания блюда."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    photo_id: Optional[uuid.UUID] = Field(None)
    price: int = Field(..., ge=0)
    cafes_id: list[uuid.UUID] = Field(default_factory=list)


class DishShortInfo(BaseModel):
    """Краткая информация о блюде."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    photo_id: Optional[uuid.UUID]


class DishInfo(DishShortInfo):
    """Схема полных данных о блюде."""

    price: int
    is_active: bool
    # В FullBaseSchemaDB Андрея поле называется create_date,
    # в OpenAPI и здесь - created_at.
    # Нужно уточнить какой имя оставим.
    created_at: datetime
    updated_at: datetime


class DishUpdate(BaseModel):
    """Схема редактирования блюда."""

    model_config = ConfigDict(extra='forbid')

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    photo_id: Optional[uuid.UUID] = Field(None)
    price: Optional[int] = Field(None, ge=0)
    cafes_id: Optional[list[uuid.UUID]] = Field(None)
    is_active: Optional[bool] = Field(None)
