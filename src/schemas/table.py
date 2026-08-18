from typing import Optional

from pydantic import ConfigDict, Field, PositiveInt

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.cafe import CafeShortInfo


class TableCreate(DescriptionScheme):
    """Схема для создания стола."""

    model_config = ConfigDict(extra='forbid')

    seat_number: PositiveInt = Field(description='Количество мест')


class TableUpdate(TableCreate):
    """Схема для обновления стола."""

    seat_number: Optional[PositiveInt] = Field(
        None,
        description='Количество мест',
    )
    is_active: Optional[bool] = Field(None, description='Активность стола')


class TableShortInfo(IdScheme, TableCreate):
    """Краткая информация о столе."""


class TableInfo(TableShortInfo, BaseInfoScheme):
    """Полная информация о столе."""

    cafe: CafeShortInfo
