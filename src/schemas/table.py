from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TableBase(BaseModel):
    """Базовая схема стола."""

    seat_number: int = Field(..., description="Количество мест", ge=1)
    description: Optional[str] = Field(None, description="Описание стола")


class TableCreate(TableBase):
    """Схема для создания стола."""


class TableUpdate(BaseModel):
    """Схема для обновления стола."""

    seat_number: Optional[int] = Field(
        None, description="Количество мест", ge=1,
    )
    description: Optional[str] = Field(None, description="Описание стола")
    is_active: Optional[bool] = Field(None, description="Активность стола")


class TableInfo(BaseModel):
    """Полная информация о столе."""

    id: UUID
    cafe_id: UUID
    cafe_name: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    seat_number: int
    created_at: datetime
    updated_at: datetime

    class Config:
        """Конфигурация Pydantic модели."""

        from_attributes = True


class TableShort(BaseModel):
    """Краткая информация о столе."""

    id: UUID
    seat_number: int

    class Config:
        """Конфигурация Pydantic модели."""

        from_attributes = True


class TableFilter(BaseModel):
    """Фильтрация столов по количеству мест и кафе."""

    # показываем только столы с is_active=True
    cafe_id: Optional[UUID] = None
    min_seat_number: Optional[int] = Field(
        None, ge=1, description="Мин. кол-во мест",
    )
    max_seat_number: Optional[int] = Field(
        None, ge=1, description="Макс. кол-во мест",
    )

    @model_validator(mode="after")
    def validate_filters(self) -> "TableFilter":
        """Проверка: мин. кол-во мест не может быть больше макс."""
        if (
            self.min_seat_number is not None
            and self.max_seat_number is not None
        ):
            if self.max_seat_number < self.min_seat_number:
                raise ValueError(
                    "Макс. кол-во мест должно быть >= мин. кол-во мест.",
                )
        return self
