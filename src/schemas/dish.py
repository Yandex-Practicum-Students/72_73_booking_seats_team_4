import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.base import BaseInfoScheme, IdScheme
from schemas.cafe import CafeShortInfo
from schemas.validators import field_cannot_be_null, validate_empty_field

from core.constants import (
    COMMON_DESCRIPTION_MAX_LENGTH,
    DISH_NAME_MAX_LENGTH,
    DISH_PRICE_DECIMAL_PLACES,
    DISH_PRICE_GT,
    DISH_PRICE_MAX_DIGITS,
)


class DishBase(BaseModel):
    """Общие поля блюда."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., max_length=DISH_NAME_MAX_LENGTH)
    description: Optional[str] = Field(None, max_length=COMMON_DESCRIPTION_MAX_LENGTH)
    photo_id: Optional[uuid.UUID] = Field(None)
    price: Decimal = Field(
        ...,
        gt=DISH_PRICE_GT,
        max_digits=DISH_PRICE_MAX_DIGITS,
        decimal_places=DISH_PRICE_DECIMAL_PLACES,
    )


class DishCreate(DishBase):
    """Схема создания блюда."""

    cafes_id: list[uuid.UUID] = Field(default_factory=list)

    check_not_empty_fields = field_validator('name', 'cafes_id')(validate_empty_field)


class DishInfo(IdScheme, DishBase, BaseInfoScheme):
    """Схема полных данных о блюде."""

    cafes: list[CafeShortInfo]


class DishUpdate(DishCreate):
    """Схема редактирования блюда."""

    name: Optional[str] = Field(None, max_length=DISH_NAME_MAX_LENGTH)
    price: Optional[Decimal] = Field(
        None,
        gt=DISH_PRICE_GT,
        max_digits=DISH_PRICE_MAX_DIGITS,
        decimal_places=DISH_PRICE_DECIMAL_PLACES,
    )
    cafes_id: Optional[list[uuid.UUID]] = Field(None)
    is_active: Optional[bool] = Field(None)

    check_not_null_fields = field_validator('name', 'cafes_id')(field_cannot_be_null)
