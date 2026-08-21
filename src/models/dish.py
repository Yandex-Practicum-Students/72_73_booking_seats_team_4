import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base
from core.constants import COMMON_DESCRIPTION_MAX_LENGTH, DISH_NAME_MAX_LENGTH


class CafeDish(Base):
    """Промежуточная таблица связи кафе и блюда (меню кафе).

    Одно блюдо может входить в меню нескольких кафе, а в одном кафе
    может быть несколько блюд.
    """

    __tablename__ = 'cafe_dishes'
    __table_args__ = (UniqueConstraint('cafe_id', 'dish_id', name='uq_cafe_dish'),)

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('cafes.id', name='fk_cafe_dishes_cafe_id'),
    )
    dish_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('dishes.id', name='fk_cafe_dishes_dish_id'),
    )


class Dish(Base):
    """Модель блюда.

    Блюдо может входить в меню нескольких кафе (связь через CafeDish).
    """

    __tablename__ = 'dishes'
    name: Mapped[str] = mapped_column(String(DISH_NAME_MAX_LENGTH), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(COMMON_DESCRIPTION_MAX_LENGTH), nullable=True)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey('medias.id', name='fk_dish_photo'),
        nullable=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
