from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Environment(StrEnum):
    """Форматы окружений для разработки."""

    DEVELOPMENT = 'development'
    PRODUCTION = 'production'


class LogLevel(StrEnum):
    """Уровни логирования, поддерживаемые приложением."""

    DEBUG = 'DEBUG'
    INFO = 'INFO'
    SUCCESS = 'SUCCESS'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


def parse_space_separated(row: str | list[str]) -> list[str]:
    """Парсит space-separated списки."""
    if isinstance(row, list):
        return row
    return [item.strip() for item in row.split() if item.strip()]


SpaceSeparatedList = Annotated[list[str], NoDecode, BeforeValidator(parse_space_separated)]


class Settings(BaseSettings):
    """Настройки приложения."""

    # Общие настройки
    title: str = 'Базовый набор FastAPI+SQLAlchemy+Postgres'
    version: str = '0.0.1'
    description: str = 'Основа для приложения'
    environment: Environment = Environment.DEVELOPMENT

    # Настройки подключения к БД
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_server: str = 'localhost'
    postgres_port: int = 5432

    # Настройки авторизации
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_lifetime_seconds: int = Field(default=3600, gt=0)

    # Настройки логирования
    log_level: LogLevel = LogLevel.DEBUG
    log_file_path: Path = BASE_DIR / '..' / 'logs' / 'app.log'
    log_rotation_size_mb: int = Field(default=10, ge=1, le=1024)
    log_retention_count: int = Field(default=4, ge=1, le=10)

    # Настройки CORS
    allowed_hosts: SpaceSeparatedList = ['http://localhost:5173', 'http://localhost:3000']
    allow_credentials: bool = True
    allowed_methods: SpaceSeparatedList = ['OPTIONS', 'GET', 'POST', 'PUT', 'PATCH']
    allowed_headers: SpaceSeparatedList = ['Authorization', 'Accept', 'Content-Type']

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '../infra/.env',
        env_file_encoding='utf-8',
        env_ignore_empty=True,
        extra='ignore',
    )

    @property
    def db_url(self) -> str:
        """Строка подключения к БД."""
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@'
            f'{self.postgres_server}:{self.postgres_port}/{self.postgres_db}'
        )


settings = Settings()
