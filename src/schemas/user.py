import uuid
from datetime import datetime
from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    model_validator,
)

from models.user import UserRole
from schemas.validators import normalize_login, normalize_phone, normalize_username

Username = Annotated[str, BeforeValidator(normalize_username)]
Phone = Annotated[str, BeforeValidator(normalize_phone)]
Login = Annotated[str, BeforeValidator(normalize_login)]


class AuthData(BaseModel):
    """Данные для входа по электронной почте или телефону."""

    login: Login = Field(
        min_length=1,
        max_length=320,
        description='Логин пользователя (email или телефон)',
    )
    password: SecretStr


class AuthToken(BaseModel):
    """JWT-токен для последующей авторизации пользователя."""

    access_token: str
    token_type: str


class UserCreate(BaseModel):
    """Схема создания пользователя."""

    model_config = ConfigDict(extra='forbid')

    username: Username = Field(..., min_length=3, max_length=64)
    email: Optional[EmailStr] = Field(None, max_length=255)
    phone: Optional[Phone] = Field(None, max_length=20)
    password: str = Field(..., min_length=8, max_length=255)
    tg_id: Optional[str] = Field(None, max_length=64)

    @model_validator(mode='after')
    def check_email_or_phone(self) -> 'UserCreate':
        """Проверяет наличие email или phone."""
        if not self.email and not self.phone:
            raise ValueError('Поле email или поле phone должно быть заполнено')
        return self


class UserShortInfo(BaseModel):
    """Краткая информация о пользователе."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: Optional[str]
    phone: Optional[str]
    tg_id: Optional[str]


class UserInfo(UserShortInfo):
    """Схема полных данных о пользователе."""

    model_config = ConfigDict(from_attributes=True)

    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Схема редактирования пользователя."""

    model_config = ConfigDict(extra='forbid')

    username: Optional[Username] = Field(None, min_length=3, max_length=64)
    email: Optional[EmailStr] = Field(None, max_length=255)
    phone: Optional[Phone] = Field(None, max_length=20)
    password: Optional[str] = Field(None, min_length=8, max_length=255)
    tg_id: Optional[str] = Field(None, max_length=64)
    role: Optional[UserRole] = Field(None)
    is_active: Optional[bool] = Field(None)
