import uuid
from typing import List, Optional

from pydantic import ConfigDict, Field

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.user import UserShortInfo

from core.constants import CAFE_ADDRESS_MAX_LENGTH, CAFE_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH


class BaseCafe(DescriptionScheme):
    """Базовая схема объекта кафе."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., max_length=CAFE_NAME_MAX_LENGTH)
    address: str = Field(..., max_length=CAFE_ADDRESS_MAX_LENGTH)
    phone: str = Field(..., max_length=PHONE_NUMBER_MAX_LENGTH)
    photo_id: Optional[uuid.UUID] = None


class CafeCreate(BaseCafe):
    """Схема создания объекта."""

    managers_id: List[int]


class CafeShortInfo(IdScheme, BaseCafe):
    """Схема для получения короткой инфо об объекте."""


class CafeInfo(CafeShortInfo, BaseInfoScheme):
    """Схема полной инфо об объекте."""

    managers: List[UserShortInfo]


class CafeUpdate(BaseCafe):
    """Схема обновления данных о кафе."""

    name: Optional[str] = Field(None, max_length=CAFE_NAME_MAX_LENGTH)
    address: Optional[str] = Field(None, max_length=CAFE_ADDRESS_MAX_LENGTH)
    phone: Optional[str] = Field(None, max_length=PHONE_NUMBER_MAX_LENGTH)
    managers_id: Optional[List[int]] = None
    is_active: Optional[bool] = None
