import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from models.user import UserRole


class UserLogin(BaseModel):
    """Схема для аутентификации по email/phone + пароль."""

    login: str = Field(..., description='Email или телефон')
    password: str = Field(..., min_length=8, max_length=255, description='Пароль')


class UserCreate(BaseModel):
    """Схема создания пользователя."""

    username: str = Field(..., min_length=3, max_length=64, description='Имя пользователя')
    email: Optional[EmailStr] = Field(None, max_length=255, description='Email')
    phone: Optional[str] = Field(None, max_length=20, description='Телефон')
    password: str = Field(..., min_length=8, max_length=255, description='Пароль')
    tg_id: Optional[str] = Field(None, max_length=64, description='Telegram ID')
    cafe_id: Optional[uuid.UUID] = Field(None, description='ID кафе')
    role: Optional[UserRole] = Field(UserRole.USER, description='Роль')

    @model_validator(mode='after')
    def check_email_or_phone(self) -> 'UserCreate':
        """Проверяет наличие email или phone."""
        if not self.email and not self.phone:
            raise ValueError('Поле email или поле phone должно быть заполнено')
        return self


class UserShortInfo(BaseModel):
    """Краткая информация о пользователе."""

    id: uuid.UUID
    username: str
    email: Optional[str]
    phone: Optional[str]
    tg_id: Optional[str]


class UserInfo(UserShortInfo):
    """Схема полных данных о пользователе."""

    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Схема редактирования пользователя."""

    username: Optional[str] = Field(None, min_length=3, max_length=64, description='Имя пользователя')
    email: Optional[EmailStr] = Field(None, max_length=255, description='Email')
    phone: Optional[str] = Field(None, max_length=20, description='Телефон')
    tg_id: Optional[str] = Field(None, max_length=64, description='Telegram ID')
    role: Optional[UserRole] = Field(None, description='Роль')
    is_active: Optional[bool] = Field(None, description='Активен ли пользователь')
    cafe_id: Optional[uuid.UUID] = Field(None, description='ID кафе')

    @model_validator(mode='after')
    def check_at_least_one_field(self) -> 'UserUpdate':
        """Проверяет, что хотя бы одно поле заполнено."""
        if all(getattr(self, field) is None for field in self.__class__.model_fields):
            raise ValueError('Хотя бы одно поле должно быть заполнено')
        return self
