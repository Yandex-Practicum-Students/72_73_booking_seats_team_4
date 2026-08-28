import uuid

from models.action import Action
from services.action import get_action_or_raise

from core.db import DBSession


async def get_action_or_404(
    action_id: uuid.UUID,
    session: DBSession,
) -> Action:
    """FastAPI-зависимость для получения существующей акции."""
    return await get_action_or_raise(action_id, session)
