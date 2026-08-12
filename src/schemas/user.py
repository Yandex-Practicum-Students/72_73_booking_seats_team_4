import uuid

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr, Field, model_validator


class UserLogin(BaseModel):
    """Схема для аутентификации по email/phone + пароль."""

    login: str = Field(..., description='Email или телефон')
    password: str = Field(..., min_length=8)


class UserCreate(schemas.BaseUserCreate):
    """Схема создания пользователя."""

    username: str = Field(..., min_length=3)
    email: EmailStr | None
    phone: str | None = Field(None, max_length=17)
    tg_id: str | None = None

    @model_validator(mode='after')
    def check_email_or_phone(self) -> 'UserCreate':
        if not self.email and not self.phone:
            raise ValueError('Одно из полей email или phone'
                             'должно быть заполнено')
        return self


class UserInfo(schemas.BaseUser[uuid.uuid4]):
    """Схема полных данных о пользователе."""


class UserRole:
    """Схема пользовательских ролей."""


class UserShortInfo:
    """Схема полных данных о пользователе."""


class UserUpdate(schemas.BaseUserUpdate):
    """Схема редактирования пользователя."""
