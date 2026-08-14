import uuid
from typing import List, Optional

from sqlalchemy import UUID, ForeignKey, String, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.user import User  # noqa

from core import base_model


class Cafe(base_model.Base, base_model.DescriptionMixin):
    """Модель Cafes."""

    name: Mapped[str] = mapped_column(String, unique=True)
    address: Mapped[str] = mapped_column(String, unique=True)
    phone: Mapped[str] = mapped_column(String, unique=True)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID,
        ForeignKey('medias.id', name='fk_cafe_photo'),
        nullable=True,
    )
    managers: Mapped[List[User]] = relationship(
        'Users',
        primaryjoin=lambda: and_(Cafe.id == User.cafe_id, User.role == 'MANAGER'),
        name='fk_cafe_managers',
    )  # noqa
