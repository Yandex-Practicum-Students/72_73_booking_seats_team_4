# from models.slots import Slot
from models.action import Action, CafeAction
from models.cafe import Cafe
from models.dish import CafeDish, Dish
from models.media import Media
from models.table import Table

from core.base_model import Base

__all__ = [
    Action,
    Cafe,
    Base,
    CafeAction,
    CafeDish,
    Dish,
    Media,
    # Slot,
    Table,
]
