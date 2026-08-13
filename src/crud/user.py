import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from schemas.user import UserCreate
from schemas.validators import normalize_login, normalize_phone

from core.user import hash_password

IDENTITY_FIELDS = ('username', 'email', 'phone', 'tg_id')


class UserAlreadyExistsError(ValueError):
    """Пользователь с одним из уникальных полей уже существует."""


class UserNotFoundError(LookupError):
    """Пользователь с переданным идентификатором не найден."""


def _normalize_identity(data: Mapping[str, Any]) -> dict[str, Any]:
    """Нормализует идентификаторы пользователя перед записью."""
    normalized = dict(data)
    if normalized.get('email') is not None:
        normalized['email'] = str(normalized['email']).strip().lower()
    if normalized.get('phone') is not None:
        normalized['phone'] = normalize_phone(normalized['phone'])
    if normalized.get('username') is not None:
        normalized['username'] = normalized['username'].strip()
    return normalized


class UserCRUD:
    """Операции с пользователями в базе данных."""

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию базы данных."""
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        """Возвращает пользователя по идентификатору."""
        return await self.session.get(User, user_id)

    async def get_or_raise(self, user_id: uuid.UUID) -> User:
        """Возвращает пользователя или сообщает, что он не найден."""
        user = await self.get(user_id)
        if user is None:
            raise UserNotFoundError
        return user

    async def get_by_login(self, login: str) -> User | None:
        """Ищет пользователя по email или телефону."""
        login = normalize_login(login)
        statement = select(User).where(
            or_(
                func.lower(User.email) == login.lower(),
                User.phone == login,
            ),
        )
        return await self.session.scalar(statement)

    async def get_all(self) -> list[User]:
        """Возвращает всех пользователей."""
        users = await self.session.scalars(select(User).order_by(User.created_at))
        return list(users.all())

    async def create(self, user_create: UserCreate) -> User:
        """Создаёт пользователя и сохраняет только хеш пароля."""
        data = _normalize_identity(user_create.model_dump())
        password = data.pop('password')
        await self._ensure_unique_identity(data)

        user = User(**data, hashed_password=hash_password(password))
        self.session.add(user)
        await self._flush_or_raise_conflict()
        await self.session.refresh(user)
        return user

    async def update(self, user: User, update_data: Mapping[str, Any]) -> User:
        """Обновляет переданные поля пользователя."""
        data = _normalize_identity(update_data)
        password = data.pop('password', None)
        await self._ensure_unique_identity(data, exclude_user_id=user.id)

        for field_name, field_value in data.items():
            setattr(user, field_name, field_value)
        if password is not None:
            user.hashed_password = hash_password(password)

        await self._flush_or_raise_conflict()
        await self.session.refresh(user)
        return user

    async def soft_delete(self, user: User) -> None:
        """Деактивирует пользователя без удаления записи из базы."""
        user.is_active = False
        await self.session.flush()

    async def _ensure_unique_identity(
        self,
        data: Mapping[str, Any],
        *,
        exclude_user_id: uuid.UUID | None = None,
    ) -> None:
        """Проверяет уникальность публичных идентификаторов."""
        conditions = [
            getattr(User, field_name) == field_value
            for field_name in IDENTITY_FIELDS
            if (field_value := data.get(field_name)) is not None
        ]
        if not conditions:
            return

        statement = select(User.id).where(or_(*conditions))
        if exclude_user_id is not None:
            statement = statement.where(User.id != exclude_user_id)
        if await self.session.scalar(statement) is not None:
            raise UserAlreadyExistsError

    async def _flush_or_raise_conflict(self) -> None:
        """Сохраняет изменения и преобразует конфликт уникальности."""
        try:
            await self.session.flush()
        except IntegrityError as error:
            await self.session.rollback()
            raise UserAlreadyExistsError from error
