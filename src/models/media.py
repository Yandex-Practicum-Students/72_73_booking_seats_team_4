import uuid

from sqlalchemy import UUID, String
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import PreBase


class Media(PreBase):
    """Модель изображения.

    Хранит метаданные загруженного файла. Сам файл сохраняется на диске,
    в базе хранится путь к нему и служебная информация.
    """

    __tablename__ = 'medias'

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
