import uuid
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from constants import MAX_ADDRESS_LNGH, MAX_CAFE_NAME_LNGH, MAX_PHONE_LNGH, MIN_STR_LNGH
from models.user import User

from src.schemas.base import BaseSchemaDB, DescriptionSchema, FullBaseSchemaDB, IsActiveSchema
from src.schemas.user import Phone


class BaseCafe(BaseModel):
    """Базовая схема объекта кафе."""

    name: str = Field(
        min_length=MIN_STR_LNGH,
        max_length=MAX_CAFE_NAME_LNGH,
        description='Название кафе',
    )
    address: str = Field(
        min_length=MIN_STR_LNGH,
        max_length=MAX_ADDRESS_LNGH,
        description='Описание кафе',
    )
    phone: Phone = Field(max_length=MAX_PHONE_LNGH, description='Телефон кафе')
    photo_id: Optional[uuid.UUID] = None


class CafeCreate(DescriptionSchema, BaseCafe):
    """Схема создания объекта."""

    managers_id: List[uuid.UUID]

    @field_validator('name', 'address', 'phone', 'managers_id')
    @classmethod
    def validate_empty_field(
        cls,
        value: str | List[uuid.UUID],
        info: ValidationInfo,
    ) -> str | List[uuid.UUID]:
        """Валидирует пустые поля."""
        if (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and not value):
            raise ValueError(f'Обязательное поле {info.field_name} не должно быть пустым.')
        return value


class CafeInfo(FullBaseSchemaDB, BaseCafe, DescriptionSchema):
    """Схема полной инфо об объекте."""

    managers: List[User]


class CafeShortInfo(BaseSchemaDB, BaseCafe, DescriptionSchema):
    """Схема для получения короткой инфо о объекте."""


class CafeUpdate(DescriptionSchema, IsActiveSchema):
    """Схема обновления."""

    name: Optional[str] = Field(
        None,
        min_length=MIN_STR_LNGH,
        max_length=MAX_CAFE_NAME_LNGH,
        description='Название кафе',
    )
    address: Optional[str] = Field(
        None,
        min_length=MIN_STR_LNGH,
        max_length=MAX_ADDRESS_LNGH,
        description='Описание кафе',
    )
    phone: Optional[str] = Field(None, max_length=MAX_PHONE_LNGH, description='Телефон кафе')
    photo_id: Optional[uuid.UUID] = None
    managers_id: Optional[List[uuid.UUID]] = None

    @field_validator('name', 'address', 'description', 'phone', 'photo_id', 'managers_id', mode='before')
    @classmethod
    def validate_null_field(
        cls,
        value: Any,
        info: ValidationInfo,
    ) -> Any:
        """Валидирует пустые, null поля."""
        if value is None:
            return value
        if isinstance(value, str) and not value.strip():
            raise ValueError(f'Поле {info.field_name} не может быть пустой строкой.')
        if isinstance(value, list) and not value:
            raise ValueError(f'Список {info.field_name} не может быть пустым.')
        return value
