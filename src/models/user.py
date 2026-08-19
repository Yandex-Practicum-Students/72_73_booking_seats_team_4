import uuid
from enum import StrEnum
from typing import Optional

from sqlalchemy import UUID, CheckConstraint, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base
from core.constants import (
    PHONE_NUMBER_MAX_LENGTH,
    USER_EMAIL_MAX_LENGTH,
    USER_PASSWORD_MAX_LENGTH,
    USER_TG_ID_MAX_LENGTH,
    USER_USERNAME_MAX_LENGTH,
)


class UserRole(StrEnum):
    """Класс описания пользовательских ролей."""

    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    USER = 'USER'


class User(Base):
    """Модель пользователя.

    - Поля email и phone - опциональны. Но хотя бы одно из них должно быть заполнено.
    - check_user_email_or_phone_not_null реализует логику:
        1. Возьми значения email и phone.
        2. Нормализуй эти значения - отбрось пробелы (BTRIM).
        3. Если нормализованное значение равно '', верни NULL, а если не равно,
           то верни это значение (NULLIF)
        4. Верни результат выполнения хотя бы одного из условий.
    - непустой cafe_id возможен только у пользователя с role='MANAGER'.
      При этом у менеджера cafe_id может быть NULL.
    """

    __table_args__ = (
        CheckConstraint(
            """
            NULLIF(BTRIM(email), '') IS NOT NULL
            OR NULLIF(BTRIM(phone), '') IS NOT NULL
            """,
            name='check_user_email_or_phone_not_null',
        ),
        CheckConstraint(
            "cafe_id IS NULL OR role = 'MANAGER'",
            name='check_user_cafe_only_for_manager',
        ),
    )

    username: Mapped[str] = mapped_column(String(USER_USERNAME_MAX_LENGTH), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(USER_EMAIL_MAX_LENGTH), nullable=True, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(PHONE_NUMBER_MAX_LENGTH), nullable=True, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(USER_PASSWORD_MAX_LENGTH))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name='user_role_enum'), default=UserRole.USER)
    tg_id: Mapped[Optional[str]] = mapped_column(String(USER_TG_ID_MAX_LENGTH), nullable=True, unique=True)
    cafe_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID,
        ForeignKey('cafes.id', name='fk_user_cafe_id_cafe'),
        nullable=True,
    )
