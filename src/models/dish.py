import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base


class CafeDish(Base):
    """
    Промежуточная таблица связи кафе и блюда (меню кафе).
    Одно блюдо может входить в меню нескольких кафе, а в одном кафе
    может быть несколько блюд.
    """

    __tablename__ = 'cafe_dishes'
    __table_args__ = (
        UniqueConstraint('cafe_id', 'dish_id', name='uq_cafe_dish'),
    )

    cafe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('cafes.id', name='fk_cafe_dishes_cafe_id'),
        nullable=False,
    )
    dish_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('dishes.id', name='fk_cafe_dishes_dish_id'),
        nullable=False,
    )


class Dish(Base):
    """
    Модель блюда.
    Блюдо может входить в меню нескольких кафе (связь через CafeDish).
    """

    __tablename__ = 'dishes'

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    # Уточни плиз (price): цена хранится у блюда (как в OpenAPI).
    # В диаграмме БД (db_diagram_13_08_2026.json) цена была в таблице cafe_dishes.
    # Сделала у блюда. Возможно поменяем.
    price: Mapped[int] = mapped_column(Integer, nullable=False)
