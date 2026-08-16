from datetime import time
from typing import Annotated, Optional

from pydantic import BeforeValidator, ConfigDict, Field, model_validator

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.cafe import CafeShortInfo
from schemas.validators import normalize_time, validate_time_range

StartTime = Annotated[time, BeforeValidator(normalize_time)]
EndTime = Annotated[time, BeforeValidator(normalize_time)]


class TimeSlotBase(DescriptionScheme):
    """Базовая схема слота."""

    start_time: StartTime = Field(description='Время начала')
    end_time: EndTime = Field(description='Время окончания')
    model_config = ConfigDict(extra='forbid')


class TimeSlotCreate(TimeSlotBase):
    """Схема для создания слота."""

    @model_validator(mode='after')
    def validate_times(self) -> 'TimeSlotCreate':
        """Проверка: время начала меньше времени окончания."""
        validate_time_range(self.start_time, self.end_time)
        return self


class TimeSlotUpdate(TimeSlotBase):
    """Схема для обновления слота."""

    start_time: Optional[StartTime] = Field(None, description='Время начала')
    end_time: Optional[EndTime] = Field(None, description='Время окончания')
    is_active: Optional[bool] = Field(None, description='Активность слота')

    @model_validator(mode='after')
    def validate_times(self) -> 'TimeSlotUpdate':
        """Проверка: время начала меньше времени окончания."""
        validate_time_range(self.start_time, self.end_time)
        return self


class TimeSlotShortInfo(IdScheme, TimeSlotBase):
    """Краткая информация о слоте."""


class TimeSlotInfo(TimeSlotShortInfo, BaseInfoScheme):
    """Полная информация о слоте."""

    cafe: CafeShortInfo
