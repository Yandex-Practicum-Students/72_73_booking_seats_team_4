from typing import Optional

from pydantic import ConfigDict, Field, PositiveInt, field_validator

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.cafe import CafeShortInfo
from schemas.validators import field_cannot_be_null


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
    check_not_null_fields = field_validator('seat_number', 'is_active')(field_cannot_be_null)


class TableShortInfo(IdScheme, TableCreate):
    """Краткая информация о столе."""


class TableInfo(TableShortInfo, BaseInfoScheme):
    """Полная информация о столе."""

    cafe: CafeShortInfo
