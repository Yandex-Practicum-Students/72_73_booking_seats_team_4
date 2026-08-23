import uuid
from typing import List, Optional

from pydantic import ConfigDict, Field, field_validator, BaseModel

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.user import Phone, UserShortInfo
from schemas.validators import field_cannot_be_null, validate_empty_field

import core.constants as constants
from core.constants import CAFE_ADDRESS_MAX_LENGTH, CAFE_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH

from core.constants import COMMON_DESCRIPTION_MAX_LENGTH


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

    managers_id: List[uuid.UUID]
    check_not_empty_fields = field_validator('name', 'address', 'phone', 'managers_id')(validate_empty_field)


class CafeShortInfo(IdScheme, BaseCafe):
    """Схема для получения короткой инфо об объекте."""


class CafeInfo(CafeShortInfo, BaseInfoScheme):
    """Схема полной инфо об объекте."""

    managers: List[UserShortInfo]= Field(default_factory=list)


class CafeUpdate(BaseModel):
    """Схема обновления данных о кафе."""

    model_config = ConfigDict(extra='forbid')

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
    phone: Optional[Phone] = Field(
        None,
        max_length=PHONE_NUMBER_MAX_LENGTH,
        description='Телефон кафе',
    )
    photo_id: Optional[uuid.UUID] = None
    description: Optional[str] = Field(
        None,
        max_length=COMMON_DESCRIPTION_MAX_LENGTH,
        description='Описание кафе',
    )
    managers_id: Optional[List[uuid.UUID]] = None
    is_active: Optional[bool] = None