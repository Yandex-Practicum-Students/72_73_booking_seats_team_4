import os
import sys
from pathlib import Path
from unittest import TestCase

os.environ.setdefault('POSTGRES_USER', 'test')
os.environ.setdefault('POSTGRES_PASSWORD', 'test')
os.environ.setdefault('POSTGRES_DB', 'test')
os.environ.setdefault('JWT_SECRET', '01234567890123456789012345678901')
os.environ.setdefault('REDIS_PASSWORD', 'test')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from tasks.celery_app import celery_app  # noqa: E402
from tasks.system import healthcheck  # noqa: E402

from core.settings import Settings  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CeleryInfrastructureTests(TestCase):
    """Проверяет базовую конфигурацию очереди задач."""

    def test_broker_url_escapes_credentials_and_default_vhost(self) -> None:
        """Данные подключения безопасно кодируются в AMQP URL."""
        app_settings = Settings(
            _env_file=None,
            postgres_user='test',
            postgres_password='test',
            postgres_db='test',
            jwt_secret='01234567890123456789012345678901',
            rabbitmq_user='test user',
            rabbitmq_password='p@ss/word',
            rabbitmq_server='localhost',
        )

        self.assertEqual(
            app_settings.celery_broker_url,
            'amqp://test%20user:p%40ss%2Fword@localhost:5672/%2F',
        )

    def test_celery_uses_json_and_emits_monitoring_events(self) -> None:
        """Worker использует безопасный формат и отдаёт события Flower."""
        self.assertEqual(celery_app.conf.task_serializer, 'json')
        self.assertEqual(celery_app.conf.accept_content, ('json',))
        self.assertTrue(celery_app.conf.task_send_sent_event)
        self.assertTrue(celery_app.conf.worker_send_task_events)
        self.assertTrue(celery_app.conf.broker_connection_retry_on_startup)

    def test_healthcheck_task_is_registered_and_returns_ok(self) -> None:
        """Проверочная задача доступна worker и выполняется без брокера."""
        celery_app.loader.import_task_module('tasks.system')

        self.assertIn('booking_seats.system.healthcheck', celery_app.tasks)
        self.assertEqual(healthcheck.run(), {'status': 'ok'})

    def test_postgres_healthcheck_reads_container_environment(self) -> None:
        """Compose не подставляет переменные Postgres из окружения хоста."""
        compose = (PROJECT_ROOT / 'infra' / 'docker-compose.yaml').read_text()

        self.assertIn(
            'pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB',
            compose,
        )
