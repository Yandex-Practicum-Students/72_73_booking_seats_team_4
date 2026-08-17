import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from schemas.base import BaseInfoScheme, IdScheme
from schemas.cafe import CafeShortInfo

from core.constants import COMMON_DESCRIPTION_MAX_LENGTH, DISH_NAME_MAX_LENGTH


class DishCreate(BaseModel):
    """Схема создания блюда."""

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., max_length=DISH_NAME_MAX_LENGTH)
    description: Optional[str] = Field(None, max_length=COMMON_DESCRIPTION_MAX_LENGTH)
    photo_id: Optional[uuid.UUID] = Field(None)
    price: NonNegativeInt
    cafes_id: list[uuid.UUID] = Field(default_factory=list)


class DishInfo(IdScheme, DishCreate, BaseInfoScheme):
    """Схема полных данных о блюде."""

    cafes_id: list[CafeShortInfo]


class DishUpdate(DishCreate):
    """Схема редактирования блюда."""

    name: Optional[str] = Field(None, max_length=DISH_NAME_MAX_LENGTH)
    price: Optional[NonNegativeInt] = Field(None)
    cafes_id: Optional[list[uuid.UUID]] = Field(None)
    is_active: Optional[bool] = Field(None)
