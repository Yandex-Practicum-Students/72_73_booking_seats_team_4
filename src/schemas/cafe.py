import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

import constants
from schemas.base import BaseInfoScheme
from schemas.user import UserShortInfo


class BaseCafe(BaseModel):
    """Базовая схема объекта кафе."""

    name: str
    address: str
    phone: str
    description: Optional[str] = Field(None, min_length=constants.DESCRIPTION_MIN_LNGH)
    photo_id: Optional[uuid.UUID] = None


class CafeCreate(BaseCafe):
    """Схема создания объекта."""

    managers_id: List[int]


class CafeShortInfo(BaseCafe):
    """Схема для получения короткой инфо об объекте."""

    id: uuid.UUID


class CafeInfo(BaseCafe, BaseInfoScheme):
    """Схема полной инфо об объекте."""

    managers: List[UserShortInfo]


class CafeUpdate(BaseModel):
    """Схема обновления."""

    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    photo_id: Optional[uuid.UUID] = None
    managers_id: Optional[List[int]] = None
    is_active: Optional[bool] = None
