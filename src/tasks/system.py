from tasks.celery_app import celery_app


@celery_app.task(name='booking_seats.system.healthcheck')
def healthcheck() -> dict[str, str]:
    """Проверить, что worker обнаруживает и выполняет задачи проекта."""
    return {'status': 'ok'}
