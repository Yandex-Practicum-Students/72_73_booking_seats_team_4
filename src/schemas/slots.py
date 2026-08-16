from datetime import time
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.slots_validators import (
    # TimeValidatorMixin,
    normalize_time,
)

StartTime = Annotated[time, BeforeValidator(normalize_time)]
EndTime = Annotated[time, BeforeValidator(normalize_time)]


class TimeSlotBase(DescriptionScheme):
    """Базовая схема слота."""

    start_time: StartTime = Field(description='Время начала')
    end_time: EndTime = Field(description='Время окончания')


class TimeSlotCreate(TimeSlotBase):
    """Схема для создания слота."""

    cafe_id: UUID = Field(description='ID кафе')


class TimeSlotUpdate(DescriptionScheme, BaseModel):
    """Схема для обновления слота."""

    start_time: Optional[StartTime] = Field(None, description='Время начала')
    end_time: Optional[EndTime] = Field(None, description='Время окончания')
    is_active: Optional[bool] = Field(None, description='Активность слота')


class TimeSlotShortInfo(IdScheme, TimeSlotBase):
    """Краткая информация о слоте."""


class TimeSlotInfo(TimeSlotShortInfo, BaseInfoScheme):
    """Полная информация о слоте."""

    cafe_id: UUID
    cafe_name: Optional[str] = None
    start_time: time
    end_time: time
    description: Optional[str] = None
