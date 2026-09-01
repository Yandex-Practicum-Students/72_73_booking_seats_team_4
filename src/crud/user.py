import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.user import User
from schemas.user import UserCreate, UserInfo, UserUpdate
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


class UserCRUD(CRUDBase[User, UserCreate, UserUpdate]):
    """Операции с пользователями в базе данных."""

    def __init__(self) -> None:
        """Инициализирует CRUD для модели пользователя."""
        super().__init__(User, UserInfo)

    async def get_or_raise(self, user_id: uuid.UUID, session: AsyncSession) -> User:
        """Возвращает пользователя или сообщает, что он не найден."""
        user = await self.get(user_id, session)
        if user is None:
            raise UserNotFoundError
        return user

    async def get_by_login(self, login: str, session: AsyncSession) -> User | None:
        """Ищет пользователя по email или телефону."""
        login = normalize_login(login)
        statement = select(User).where(
            or_(
                func.lower(User.email) == login.lower(),
                User.phone == login,
            ),
        )
        return await session.scalar(statement)

    async def get_all(self, session: AsyncSession) -> list[User]:
        """Возвращает всех пользователей."""
        users = await session.scalars(select(User).order_by(User.created_at))
        return users.all()

    async def create(self, user_create: UserCreate, session: AsyncSession) -> User:
        """Создаёт пользователя и сохраняет только хеш пароля."""
        data = _normalize_identity(user_create.model_dump())
        password = data.pop('password')
        await self._ensure_unique_identity(data, session)

        user = User(**data, hashed_password=hash_password(password))
        session.add(user)
        await self._commit_or_raise_conflict(session)
        await session.refresh(user)
        return user

    async def update(
        self,
        user: User,
        update_data: UserUpdate | Mapping[str, Any],
        session: AsyncSession,
    ) -> User:
        """Обновляет переданные поля пользователя."""
        raw_data = (
            update_data.model_dump(exclude_unset=True) if isinstance(update_data, UserUpdate) else update_data
        )
        data = _normalize_identity(raw_data)
        password = data.pop('password', None)
        await self._ensure_unique_identity(
            data,
            session,
            exclude_user_id=user.id,
        )

        for field_name, field_value in data.items():
            setattr(user, field_name, field_value)
        if password is not None:
            user.hashed_password = hash_password(password)

        await self._commit_or_raise_conflict(session)
        await session.refresh(user)
        return user

    async def _ensure_unique_identity(
        self,
        data: Mapping[str, Any],
        session: AsyncSession,
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
        if await session.scalar(statement) is not None:
            raise UserAlreadyExistsError

    @staticmethod
    async def _commit_or_raise_conflict(session: AsyncSession) -> None:
        """Сохраняет изменения и преобразует конфликт уникальности."""
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise UserAlreadyExistsError from error


user_crud = UserCRUD()
