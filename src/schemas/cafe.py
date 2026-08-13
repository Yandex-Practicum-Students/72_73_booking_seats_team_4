import uuid
from typing import List, Optional

from pydantic import BaseModel

from src.schemas.base import BaseSchemaDB, DescriptionSchema, FullBaseSchemaDB, IsActiveSchema

# from models.user import Users


class ManagersCafe(BaseModel):
    """Схема менеджеров кафе."""

    managers_id: List[uuid.UUID]


class BaseCafe(BaseModel):
    """Базовая схема объекта кафе."""

    name: str
    address: str
    phone: str
    photo_id: Optional[uuid.UUID] = None


class CafeCreate(DescriptionSchema, ManagersCafe, BaseCafe):
    """Схема создания объекта."""

    pass


class CafeInfo(FullBaseSchemaDB, BaseCafe, IsActiveSchema, DescriptionSchema):
    """Схема полной инфо об объекте."""

    pass
    # managers: List[Users]


class CafeShortInfo(BaseSchemaDB, BaseCafe, DescriptionSchema):
    """Схема для получения короткой инфо о объекте."""

    pass


class CafeUpdate(DescriptionSchema, IsActiveSchema):
    """Схема обновления."""

    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    photo_id: Optional[uuid.UUID] = None
    managers_id: Optional[List[uuid.UUID]] = None
