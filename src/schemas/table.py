from typing import Optional
from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseModel, BaseSchemaDB, DescriptionSchema, FullBaseSchemaDB, IsActiveSchema


class TableBase(BaseModel):
    """Базовая схема стола."""

    seat_number: int = Field(description='Количество мест', ge=1)


class TableCreate(DescriptionSchema, TableBase):
    """Схема для создания стола."""


class TableUpdate(DescriptionSchema, IsActiveSchema):
    """Схема для обновления стола."""

    seat_number: Optional[int] = Field(
        None,
        description='Количество мест',
        ge=1,
    )


class TableShort(BaseSchemaDB):
    """Краткая информация о столе."""

    seat_number: int


class TableInfo(FullBaseSchemaDB, DescriptionSchema):
    """Полная информация о столе."""

    cafe_id: UUID
    cafe_name: Optional[str] = None
    seat_number: int
