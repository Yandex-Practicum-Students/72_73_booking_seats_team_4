from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas.base import BaseInfoScheme, DescriptionScheme
from schemas.cafe import CafeShortInfo


class TableCreate(DescriptionScheme, BaseModel):
    """Схема для создания стола."""

    model_config = ConfigDict(extra='forbid')

    seat_number: int = Field(description='Количество мест', ge=1)


class TableUpdate(BaseModel):
    """Схема для обновления стола."""

    model_config = ConfigDict(extra='forbid')

    seat_number: Optional[int] = Field(
        None,
        description='Количество мест',
        ge=1,
    )
    description: Optional[str] = Field(None, description='Описание стола')
    is_active: Optional[bool] = Field(None, description='Активность стола')


class TableShortInfo(TableCreate):
    """Краткая информация о столе."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID


class TableInfo(TableShortInfo, BaseInfoScheme):
    """Полная информация о столе."""

    cafe: CafeShortInfo
