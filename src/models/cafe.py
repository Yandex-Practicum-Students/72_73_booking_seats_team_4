import uuid

from sqlalchemy import UUID, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core import base_model


class CafeModel(base_model.Base, base_model.DescriptionMixin):
    """Модель кафе."""

    __tablename__ = 'cafes'
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    photo_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('media.id'), nullable=True)
    managers_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id'), nullable=False)
