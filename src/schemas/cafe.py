import uuid
from typing import List, Optional

from pydantic import BaseModel

from models.user import User  # noqa

from src.schemas.base import BaseSchemaDB, DescriptionSchema, FullBaseSchemaDB, IsActiveSchema


class BaseCafe(BaseModel):
    """Базовая схема объекта кафе."""

    name: str
    address: str
    phone: str
    photo_id: Optional[uuid.UUID] = None


class CafeCreate(DescriptionSchema, BaseCafe):
    """Схема создания объекта."""

    managers_id: List[uuid.UUID]


class CafeInfo(FullBaseSchemaDB, BaseCafe, IsActiveSchema, DescriptionSchema):
    """Схема полной инфо об объекте."""

    managers: List[User]  # noqa


class CafeShortInfo(BaseSchemaDB, BaseCafe, DescriptionSchema):
    """Схема для получения короткой инфо о объекте."""


class CafeUpdate(DescriptionSchema, IsActiveSchema):
    """Схема обновления."""

    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    photo_id: Optional[uuid.UUID] = None
    managers_id: Optional[List[uuid.UUID]] = None
