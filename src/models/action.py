import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base
from core.constants import ACTION_DESCRIPTION_MAX_LENGTH


class CafeAction(Base):
    """Промежуточная таблица связи кафе и акции.

    Одна акция может действовать в нескольких кафе, а в одном кафе
    может быть несколько акций.
    """

    __tablename__ = 'cafe_actions'
    __table_args__ = (UniqueConstraint('cafe_id', 'action_id', name='uq_cafe_action'),)
    cafe_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('cafes.id', name='fk_cafe_actions_cafe_id'),
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey('actions.id', name='fk_cafe_actions_action_id'),
    )


class Action(Base):
    """Модель акции.

    Акция может действовать в нескольких кафе (связь через CafeAction).
    """

    description: Mapped[str] = mapped_column(String(ACTION_DESCRIPTION_MAX_LENGTH), unique=True)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey('medias.id', name='fk_action_photo'),
        nullable=True,
    )
