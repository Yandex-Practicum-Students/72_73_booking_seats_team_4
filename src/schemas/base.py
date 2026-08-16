import uuid
from datetime import datetime

from pydantic import BaseModel

# class BaseScheme(BaseModel):
#     """Базовая схема с запретом на редактирование недоступных полей."""

#     model_config = ConfigDict(extra='forbid')


# class DescriptionScheme(BaseScheme):
#     """Добавляет поле description."""

#     description: Optional[str] = Field(min_length=constants.DESCRIPTION_MIN_LNGH)


class BaseInfoScheme(BaseModel):
    """Схема общих полей для всех подробных инфо-схем."""

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


# class DescriptionScheme(BaseModel):
#     """Добавляет поле description."""

#     description: Optional[str] = Field(None, min_length=constants.DESCRIPTION_MIN_LNGH)


# class IsActiveScheme(BaseScheme):
#     """Схема для добавления поля is_active."""

#     is_active: Optional[bool] = None


# class BaseSchemeDB(BaseModel):
#     """Добавляет поле id."""

#     id: uuid.UUID

#     # model_config = ConfigDict(extra='forbid')
#     model_config = ConfigDict(from_attributes=True, extra='forbid')
