import uuid
from enum import StrEnum
from typing import Optional

from sqlalchemy import UUID, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base


class UserRole(StrEnum):
    """Класс описания пользовательских ролей."""

    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    USER = 'USER'


class User(Base):
    """Модель пользователя."""

    username: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True)
    password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name='user_role_enum'),
        server_default=UserRole.USER.value,
        default=UserRole.USER,
    )
    tg_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    cafe_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID,
        ForeignKey('cafe.id', name='fk_user_cafe_id_cafe'),
        nullable=True,
    )
