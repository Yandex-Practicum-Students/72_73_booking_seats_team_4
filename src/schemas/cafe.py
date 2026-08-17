import uuid
from typing import Any, List, Optional

from pydantic import ConfigDict, Field, ValidationInfo, field_validator
from user import Phone

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.user import UserShortInfo

import src.core.constants as constants
from core.constants import CAFE_ADDRESS_MAX_LENGTH, CAFE_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH


class BaseCafe(DescriptionScheme):
    """Базовая схема объекта кафе."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(
        ...,
        min_length=constants.MIN_STR_LNGH,
        max_length=CAFE_NAME_MAX_LENGTH,
        description='Название кафе',
    )
    address: str = Field(
        ...,
        max_length=CAFE_ADDRESS_MAX_LENGTH,
        description='Адрес кафе',
    )
    phone: Phone = Field(
        ...,
        max_length=PHONE_NUMBER_MAX_LENGTH,
        description='Телефон кафе',
    )
    photo_id: Optional[uuid.UUID] = None


class CafeCreate(BaseCafe):
    """Схема создания объекта."""

    managers_id: List[int]

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


class CafeShortInfo(IdScheme, BaseCafe):
    """Схема для получения короткой инфо об объекте."""


class CafeInfo(CafeShortInfo, BaseInfoScheme):
    """Схема полной инфо об объекте."""

    managers: List[UserShortInfo]


class CafeUpdate(BaseCafe):
    """Схема обновления данных о кафе."""

    name: Optional[str] = Field(
        None,
        min_length=constants.MIN_STR_LNGH,
        max_length=CAFE_NAME_MAX_LENGTH,
        description='Название кафе',
    )
    address: Optional[str] = Field(
        None,
        max_length=CAFE_ADDRESS_MAX_LENGTH,
        description='Адрес кафе',
    )
    phone: Optional[Phone] = Field(None, max_length=PHONE_NUMBER_MAX_LENGTH, description='Телефон кафе')
    managers_id: Optional[List[int]] = None
    is_active: Optional[bool] = None

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
