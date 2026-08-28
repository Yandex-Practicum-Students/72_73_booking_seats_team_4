import uuid

from models.dish import Dish
from services.dish import get_dish_or_raise

from core.db import DBSession


async def get_dish_or_404(
    dish_id: uuid.UUID,
    session: DBSession,
) -> Dish:
    """FastAPI-зависимость для получения существующего блюда."""
    return await get_dish_or_raise(dish_id, session)
