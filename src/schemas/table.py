from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.cafe import CafeShortInfo


class TableCreate(DescriptionScheme, BaseModel):
    """Схема для создания стола."""

    model_config = ConfigDict(extra='forbid')

    seat_number: int = Field(description='Количество мест', ge=1)


class TableUpdate(DescriptionScheme):
    """Схема для обновления стола."""

    model_config = ConfigDict(extra='forbid')

    seat_number: Optional[int] = Field(
        None,
        description='Количество мест',
        ge=1,
    )
    is_active: Optional[bool] = Field(None, description='Активность стола')


class TableShortInfo(IdScheme, TableCreate):
    """Краткая информация о столе."""


class TableInfo(TableShortInfo, BaseInfoScheme):
    """Полная информация о столе."""

    cafe: CafeShortInfo
