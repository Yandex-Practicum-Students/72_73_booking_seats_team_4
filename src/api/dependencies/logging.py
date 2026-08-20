from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from typing import Annotated, Any

from fastapi import Depends
from loguru import logger

from models.user import User

from core.user import get_current_user, get_current_user_or_forbidden


@contextmanager
def user_log_context(user: User) -> Generator[User, Any, None]:
    """Контекстный менеджер.

    Добавляет данные текущего пользователя в контекст Loguru.
    """
    with logger.contextualize(
        user_id=str(user.id),
        username=user.username,
    ):
        yield user


async def get_current_user_with_logging(
    user: Annotated[User, Depends(get_current_user)],
) -> AsyncGenerator[User, None]:
    """Обёртка над get_current_user."""
    with user_log_context(user):
        yield user


async def get_me_user_with_logging(
    user: Annotated[User, Depends(get_current_user_or_forbidden)],
) -> AsyncGenerator[User, None]:
    """Обёртка над get_current_user_or_forbidden."""
    with user_log_context(user):
        yield user
