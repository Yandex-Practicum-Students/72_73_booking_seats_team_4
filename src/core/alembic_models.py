# from models.slots import Slot

from models.action import Action, CafeAction
from models.dish import CafeDish, Dish
from models.table import Table

from core.base_model import Base

__all__ = [
    Action,
    Base,
    CafeAction,
    CafeDish,
    Dish,
    # Slot,
    Table,
]
