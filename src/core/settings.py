from enum import StrEnum
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Environment(StrEnum):
    """Форматы окружений для разработки."""

    DEVELOPMENT = 'development'
    PRODUCTION = 'production'


def parse_space_separated(row: str | list[str]) -> list[str]:
    """Парсит space-separated списки."""
    if isinstance(row, list):
        return row
    return [item.strip() for item in row.split() if item.strip()]


SpaceSeparatedList = Annotated[list[str], NoDecode, BeforeValidator(parse_space_separated)]


class Settings(BaseSettings):
    """Настройки приложения."""

    # Общие настройки
    title: str = 'Система бронирования мест в кафе'
    version: str = '0.0.3'
    description: str = (
        'API для управления кафе, пользователями, меню и бронированиями.'
    )
    api_v1_prefix: str = '/api/v1'
    environment: Environment = Environment.DEVELOPMENT

    # Настройки подключения к БД
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_server: str = 'localhost'
    postgres_port: int = 5432

    # Настройки RabbitMQ и Celery
    rabbitmq_user: str = 'guest'
    rabbitmq_password: SecretStr = SecretStr('guest')
    rabbitmq_server: str = 'localhost'
    rabbitmq_port: int = Field(default=5672, ge=1, le=65535)
    rabbitmq_vhost: str = '/'
    celery_task_default_queue: str = Field(default='booking_notifications', min_length=1)
    celery_broker_heartbeat: int = Field(default=30, gt=0)

    # Настройки авторизации
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_lifetime_seconds: int = Field(default=3600, gt=0)

    # Настройки логирования
    log_level: str = 'INFO'
    log_file_path: Path = BASE_DIR / '..' / 'logs' / 'app.log'
    log_rotation_size_mb: int = Field(default=10, ge=1, le=1024)
    log_retention_count: int = Field(default=4, ge=1, le=10)

    # Настройки CORS
    allowed_hosts: SpaceSeparatedList = ['http://localhost:5173', 'http://localhost:3000']
    allow_credentials: bool = True
    allowed_methods: SpaceSeparatedList = ['OPTIONS', 'GET', 'POST', 'PUT', 'PATCH']
    allowed_headers: SpaceSeparatedList = ['Authorization', 'Accept', 'Content-Type']

    # Настройки SMTP
    smtp_host: str = 'smtp.yandex.ru'
    smtp_port: int = 465
    smtp_user: str = 'smtp_user'
    smtp_password: str = 'smtp_pass'
    smtp_from_email: str = 'noreply@yourdomain.com'

    # Настройка Redis
    max_connections: int = 10
    decode_responses: bool = True
    redis_password: str
    redis_port: int = 6379
    redis_cache_expire_seconds: int = 3600
    redis_url: str = 'redis://localhost:6379'

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

    @property
    def celery_broker_url(self) -> str:
        """Строка подключения Celery к RabbitMQ."""
        user = quote(self.rabbitmq_user, safe='')
        password = quote(self.rabbitmq_password.get_secret_value(), safe='')
        vhost = quote(self.rabbitmq_vhost, safe='')
        return f'amqp://{user}:{password}@{self.rabbitmq_server}:{self.rabbitmq_port}/{vhost}'


settings = Settings()
