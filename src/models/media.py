from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.base_model import Base


class Media(Base):
    """Модель изображения.

    Хранит метаданные загруженного файла. Сам файл сохраняется на диске,
    в базе хранится путь к нему и служебная информация.
    """

    __tablename__ = 'medias'

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
