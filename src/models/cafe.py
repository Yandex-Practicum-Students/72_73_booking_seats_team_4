import uuid
from typing import List, Optional

from sqlalchemy import UUID, ForeignKey, String, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from constants import MAX_ADDRESS_LNGH, MAX_CAFE_NAME_LNGH, MAX_PHONE_LNGH
from models.user import User

from core import base_model


class Cafe(base_model.Base, base_model.DescriptionMixin):
    """Модель Cafes."""

    name: Mapped[str] = mapped_column(String(MAX_CAFE_NAME_LNGH), unique=True)
    address: Mapped[str] = mapped_column(String(MAX_ADDRESS_LNGH), unique=True)
    phone: Mapped[str] = mapped_column(String(MAX_PHONE_LNGH), unique=True)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID,
        ForeignKey('medias.id', name='fk_cafe_photo'),
        nullable=True,
    )
    managers: Mapped[List[User]] = relationship(
        'User',
        primaryjoin=lambda: and_(Cafe.id == User.cafe_id, User.role == 'MANAGER'),
    )
