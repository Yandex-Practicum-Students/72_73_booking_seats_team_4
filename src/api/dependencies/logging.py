from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from loguru import logger

from models.user import User

from core.user import get_current_user


async def user_logging_context(
    user: Annotated[User, Depends(get_current_user)],
) -> AsyncGenerator[User, None]:
    """Добавляет данные пользователя в контекст Loguru."""
    with logger.contextualize(
        user_id=str(user.id),
        username=user.username,
    ):
        yield user
