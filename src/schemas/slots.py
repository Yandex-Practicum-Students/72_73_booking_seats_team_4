from datetime import time
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BeforeValidator, Field

from core.base_model import Base
from src.schemas.slots_validators import TimeValidatorMixin, normalize_time

StartTime = Annotated[time, BeforeValidator(normalize_time)]
EndTime = Annotated[time, BeforeValidator(normalize_time)]


class SlotBase(TimeValidatorMixin, Base):
    """Базовая схема слота."""

    start_time: StartTime = Field(description="Время начала")
    end_time: EndTime = Field(description="Время окончания")
    description: Optional[str] = Field(None, description="Описание слота")


class SlotCreate(SlotBase):
    """Схема для создания слота."""

    cafe_id: UUID = Field(description="ID кафе")


class SlotUpdate(SlotBase):
    """Схема для обновления слота."""

    start_time: Optional[StartTime] = Field(None, description="Время начала")
    end_time: Optional[EndTime] = Field(None, description="Время окончания")
    is_active: Optional[bool] = Field(None, description="Активность слота")


class SlotInfo(Base):
    """Полная информация о слоте."""

    cafe_id: UUID
    cafe_name: Optional[str] = None
    start_time: time
    end_time: time
    description: Optional[str] = None

    class Config:
        """Конфигурация Pydantic модели."""

        from_attributes = True


class SlotShort(Base):
    """Краткая информация о слоте."""

    start_time: time
    end_time: time

    class Config:
        """Конфигурация Pydantic модели."""

        from_attributes = True
