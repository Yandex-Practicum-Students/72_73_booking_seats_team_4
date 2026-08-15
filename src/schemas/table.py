from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TableBase(BaseModel):
    """Базовая схема стола."""

    seat_number: int = Field(description='Количество мест', ge=1)
    description: Optional[str] = Field(None, description='Описание стола')


class TableCreate(TableBase):
    """Схема для создания стола."""


class TableUpdate(BaseModel):
    """Схема для обновления стола."""

    seat_number: Optional[int] = Field(
        None, description='Количество мест', ge=1,
    )
    description: Optional[str] = Field(None, description='Описание стола')
    is_active: Optional[bool] = Field(None, description='Активность стола')


class TableShort(BaseModel):
    """Краткая информация о столе."""

    id: UUID
    seat_number: int

    class Config:
        """Конфигурация Pydantic модели."""

        from_attributes = True


class TableInfo(TableShort):
    """Полная информация о столе."""

    cafe_id: UUID
    cafe_name: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        """Конфигурация Pydantic модели."""

        from_attributes = True
