from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from models.user import UserRole
from schemas.base import BaseInfoScheme, IdScheme
from schemas.validators import field_cannot_be_null, normalize_login, normalize_phone, normalize_username

from core.constants import (
    AUTH_DATA_LOGIN_MAX_LENGTH,
    COMMON_MIN_LENGTH,
    PHONE_NUMBER_MAX_LENGTH,
    USER_EMAIL_MAX_LENGTH,
    USER_PASSWORD_MAX_LENGTH,
    USER_PASSWORD_MIN_LENGTH,
    USER_TG_ID_MAX_LENGTH,
    USER_USERNAME_MAX_LENGTH,
)

Username = Annotated[str, BeforeValidator(normalize_username)]
Phone = Annotated[str, BeforeValidator(normalize_phone)]
Login = Annotated[str, BeforeValidator(normalize_login)]


class AuthData(BaseModel):
    """Данные для входа по электронной почте или телефону."""

    login: Login = Field(
        min_length=COMMON_MIN_LENGTH,
        max_length=AUTH_DATA_LOGIN_MAX_LENGTH,
        description='Логин пользователя (email или телефон)',
    )
    password: SecretStr


class AuthToken(BaseModel):
    """JWT-токен для последующей авторизации пользователя."""

    access_token: str
    token_type: str


class UserBase(BaseModel):
    """Базовая схема пользователя."""

    model_config = ConfigDict(extra='forbid')

    username: Username = Field(..., min_length=COMMON_MIN_LENGTH, max_length=USER_USERNAME_MAX_LENGTH)
    email: Optional[EmailStr] = Field(None, max_length=USER_EMAIL_MAX_LENGTH)
    phone: Optional[Phone] = Field(None, max_length=PHONE_NUMBER_MAX_LENGTH)
    tg_id: Optional[str] = Field(None, max_length=USER_TG_ID_MAX_LENGTH)


class UserCreate(UserBase):
    """Схема создания пользователя."""

    password: str = Field(..., min_length=USER_PASSWORD_MIN_LENGTH, max_length=USER_PASSWORD_MAX_LENGTH)

    @model_validator(mode='after')
    def check_email_or_phone(self) -> 'UserCreate':
        """Проверяет наличие email или phone."""
        if not self.email and not self.phone:
            raise ValueError('Поле email или поле phone должно быть заполнено')
        return self


class UserShortInfo(IdScheme, UserBase):
    """Краткая информация о пользователе."""


class UserInfo(UserShortInfo, BaseInfoScheme):
    """Схема полных данных о пользователе."""

    role: UserRole


class UserUpdate(UserBase):
    """Схема редактирования пользователя."""

    username: Optional[Username] = Field(
        None,
        min_length=COMMON_MIN_LENGTH,
        max_length=USER_USERNAME_MAX_LENGTH,
    )
    password: Optional[str] = Field(
        None,
        min_length=USER_PASSWORD_MIN_LENGTH,
        max_length=USER_PASSWORD_MAX_LENGTH,
    )
    role: Optional[UserRole] = Field(None)
    is_active: Optional[bool] = Field(None)
    check_not_null_fields = field_validator('username', 'password')(field_cannot_be_null)
