import uuid
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from schemas.base import BaseInfoScheme, DescriptionScheme, IdScheme
from schemas.user import UserShortInfo


class BaseCafe(DescriptionScheme):
    """Базовая схема объекта кафе."""

    name: str
    address: str
    phone: str
    photo_id: Optional[uuid.UUID] = None


class CafeCreate(BaseCafe):
    """Схема создания объекта."""

    model_config = ConfigDict(extra='forbid')

    managers_id: List[int]


class CafeShortInfo(IdScheme, BaseCafe):
    """Схема для получения короткой инфо об объекте."""


class CafeInfo(CafeShortInfo, BaseInfoScheme):
    """Схема полной инфо об объекте."""

    managers: List[UserShortInfo]


class CafeUpdate(BaseModel):
    """Схема обновления данных о кафе."""

    model_config = ConfigDict(extra='forbid')

    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    photo_id: Optional[uuid.UUID] = None
    managers_id: Optional[List[int]] = None
    is_active: Optional[bool] = None
