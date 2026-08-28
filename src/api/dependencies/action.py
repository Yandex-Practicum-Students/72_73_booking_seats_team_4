import uuid

from fastapi import HTTPException, status

from models.action import Action
from services.action import get_action_or_raise
from services.errors import EntityNotFoundError

from core.db import DBSession


async def get_action_or_404(
    action_id: uuid.UUID,
    session: DBSession,
) -> Action:
    """FastAPI-зависимость для получения существующей акции."""
    try:
        return await get_action_or_raise(action_id, session)
    except EntityNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
