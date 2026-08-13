from datetime import time, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator



class TimeValidatorMixin:
    """Миксин для валидации временных интервалов."""

    start_time: Optional[time] = None
    end_time: Optional[time] = None
    @model_validator(mode="after")
    def validate_times(self) -> "TimeValidatorMixin":
        """Проверка: время начала меньше времени окончания."""
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("Время начала меньше должно быть меньше времени окончания")
        return self


class SlotBase(TimeValidatorMixin, BaseModel):
    """Базовая схема слота."""
    start_time: time = Field(..., description="Время начала")
    end_time: time = Field(..., description="Время окончания")
    description: Optional[str] = Field(None, description="Описание слота")

class SlotCreate(SlotBase):
    """Схема для создания слота."""
    cafe_id: UUID = Field(..., description="ID кафе")


class SlotUpdate(TimeValidatorMixin, BaseModel):
    """Схема для обновления слота."""
    start_time: Optional[time] = Field(None, description="Время начала")
    end_time: Optional[time] = Field(None, description="Время окончания")
    description: Optional[str] = Field(None, description="Описание слота")
    is_active: Optional[bool] = Field(None, description="Активность слота")


class SlotInfo(BaseModel):
    """Полная информация о слоте."""
    id: UUID
    cafe_id: UUID
    cafe_name: Optional[str] = None
    start_time: time
    end_time: time
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SlotShort(BaseModel):
    """Краткая информация о слоте."""
    id: UUID
    start_time: time
    end_time: time

    class Config:
        from_attributes = True




