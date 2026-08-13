import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src import constants


class BaseSchema(BaseModel):
    """Базовая схема с запретом на редактирование недоступных полей."""

    model_config = ConfigDict(extra='forbid')


class DescriptionSchema(BaseSchema):
    """Добавляет поле description."""

    description: Optional[str] = Field(min_length=constants.DESCRIPTION_MIN_LNGH)


class IsActiveSchema(BaseSchema):
    """Схема для добавления поля is_active."""

    is_active: bool


class BaseSchemaDB(BaseSchema):
    """Добавляет поле id."""

    id: uuid.UUID


class FullBaseSchemaDB(BaseSchemaDB, IsActiveSchema):
    """Схема для возвращения полной таблицы."""

    create_date: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
