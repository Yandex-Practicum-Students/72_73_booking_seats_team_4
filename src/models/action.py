import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base


class CafeAction(Base):
    """Промежуточная таблица связи кафе и акции.

    Одна акция может действовать в нескольких кафе, а в одном кафе
    может быть несколько акций.
    """

    __tablename__ = 'cafe_actions'
    __table_args__ = (
        UniqueConstraint('cafe_id', 'action_id', name='uq_cafe_action'),
    )
    cafe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('cafes.id', name='fk_cafe_actions_cafe_id'),
        nullable=False,
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('actions.id', name='fk_cafe_actions_action_id'),
        nullable=False,
    )


class Action(Base):
    """Модель акции.

    Акция может действовать в нескольких кафе (связь через CafeAction).
    """

    # Уточни плиз: у Action description ОБЯЗАТЕЛЬНЫЙ (nullable=False) по OpenAPI.
    # DescriptionMixin делает description nullable=True - для Action не подходит.
    # Поэтому объявила отдельно, а не через миксин.
    description: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
