from enum import StrEnum
from typing import Optional

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.base_model import Base


class UserRole(StrEnum):
    """Класс описания пользовательских ролей."""

    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    USER = 'USER'


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Модель пользователя."""

    username: Mapped[str] = mapped_column(String(64), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(17), nullable=True,
                                                 unique=True)
    role: Mapped[UserRole] = mapped_column(String(16), default=UserRole.USER)
    tg_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True,
                                                 unique=True)
