from pathlib import Path
from unittest import TestCase

from tasks.celery_app import celery_app
from tasks.system import healthcheck

from core.settings import Settings

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
        self.assertTrue(
            celery_app.conf.worker_cancel_long_running_tasks_on_connection_loss,
        )

    def test_notification_tasks_are_registered(self) -> None:
        """Worker обнаруживает задачи отправки и диспетчер напоминаний."""
        celery_app.loader.import_default_modules()

        self.assertIn(
            'booking.notifications.send_notification',
            celery_app.tasks,
        )
        self.assertIn(
            'booking.notifications.process_pending_due_notifications',
            celery_app.tasks,
        )

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

    def test_compose_starts_celery_beat(self) -> None:
        """Compose запускает отдельный планировщик отложенных напоминаний."""
        compose = (PROJECT_ROOT / 'infra' / 'docker-compose.yaml').read_text()

        self.assertIn('celery-beat:', compose)
        self.assertIn('      - beat\n', compose)
