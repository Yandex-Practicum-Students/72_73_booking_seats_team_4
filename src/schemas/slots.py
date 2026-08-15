from datetime import time
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field

from src.schemas.base import BaseSchemaDB, DescriptionSchema, FullBaseSchemaDB
from src.schemas.validators import TimeValidatorMixin, normalize_time

StartTime = Annotated[time, BeforeValidator(normalize_time)]
EndTime = Annotated[time, BeforeValidator(normalize_time)]


class SlotBase(TimeValidatorMixin, BaseModel , DescriptionSchema):
    """Базовая схема слота."""

    start_time: StartTime = Field(description='Время начала')
    end_time: EndTime = Field(description='Время окончания')


class SlotCreate(SlotBase):
    """Схема для создания слота."""

    cafe_id: UUID = Field(description='ID кафе')


class SlotUpdate(SlotBase):
    """Схема для обновления слота."""

    start_time: Optional[StartTime] = Field(None, description='Время начала')
    end_time: Optional[EndTime] = Field(None, description='Время окончания')
    is_active: Optional[bool] = Field(None, description='Активность слота')


class SlotShort(BaseSchemaDB, SlotBase):
    """Краткая информация о слоте."""


class SlotInfo(FullBaseSchemaDB, SlotBase):
    """Полная информация о слоте."""

    cafe_id: UUID = Field(description='ID кафе')
    cafe_name: Optional[str] = Field(None, description='Название кафе')
