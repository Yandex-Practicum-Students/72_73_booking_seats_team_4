import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import UUID, ForeignKey, String, and_
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.user import User

from core import base_model
from core.constants import CAFE_ADDRESS_MAX_LENGTH, CAFE_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH

if TYPE_CHECKING:
    from models.slots import Slot
    from models.table import Table


class Cafe(base_model.Base, base_model.DescriptionMixin):
    """Модель Cafes."""

    name: Mapped[str] = mapped_column(String(CAFE_NAME_MAX_LENGTH), unique=True)
    address: Mapped[str] = mapped_column(String(CAFE_ADDRESS_MAX_LENGTH), unique=True)
    phone: Mapped[str] = mapped_column(String(PHONE_NUMBER_MAX_LENGTH), unique=True)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID,
        ForeignKey('medias.id', name='fk_cafe_photo'),
        nullable=True,
    )
    managers: Mapped[List[User]] = relationship(
        'User',
        primaryjoin="and_(Cafe.id == User.cafe_id, User.role == 'MANAGER')",
    )
    tables: Mapped[List['Table']] = relationship(
        'Table',
        back_populates='cafe',
        lazy='selectin',
    )
    slots: Mapped[List['Slot']] = relationship(
        'Slot',
        back_populates='cafe',
        lazy='selectin',
    )
