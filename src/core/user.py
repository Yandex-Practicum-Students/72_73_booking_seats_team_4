import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User

from core.db import get_session
from core.settings import settings

JWT_ALGORITHM = 'HS256'

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash('dummy-password-for-timing-protection')

bearer_scheme = HTTPBearer(
    bearerFormat='JWT',
    scheme_name='bearerAuth',
    auto_error=False,
)


def hash_password(password: str) -> str:
    """Хеширует пароль перед сохранением в базе данных."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> tuple[bool, str | None]:
    """Проверяет пароль и при необходимости обновляет его хеш."""
    return password_hash.verify_and_update(password, hashed_password)


def create_access_token(user_id: uuid.UUID) -> str:
    """Создаёт подписанный JWT для пользователя."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.jwt_lifetime_seconds,
    )
    return jwt.encode(
        {'sub': str(user_id), 'exp': expires_at},
        settings.jwt_secret.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def _unauthorized_error() -> HTTPException:
    """Формирует единый ответ для ошибок авторизации."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Не удалось проверить данные авторизации.',
        headers={'WWW-Authenticate': 'Bearer'},
    )


def decode_access_token(token: str) -> uuid.UUID:
    """Проверяет JWT и возвращает идентификатор пользователя."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={'require': ['sub', 'exp']},
        )
        return uuid.UUID(payload['sub'])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise _unauthorized_error() from error


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: AsyncSession = Depends(get_session),
) -> User:
    """Возвращает активного пользователя из Bearer JWT."""
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise _unauthorized_error()

    user_id = decode_access_token(credentials.credentials)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized_error()
    return user


async def get_current_user_or_forbidden(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: AsyncSession = Depends(get_session),
) -> User:
    """Возвращает пользователя или ошибку 403 для ручек /users/me."""
    try:
        return await get_current_user(credentials, session)
    except HTTPException as error:
        if error.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Доступ запрещён.',
        ) from error
