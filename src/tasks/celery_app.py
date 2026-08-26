from celery import Celery

from core.settings import settings

celery_app = Celery(
    'booking_seats',
    broker=settings.celery_broker_url,
    include=('tasks.system', 'tasks.notifications'),
)

celery_app.conf.update(
    accept_content=('json',),
    broker_connection_retry_on_startup=True,
    broker_heartbeat=settings.celery_broker_heartbeat,
    enable_utc=True,
    result_serializer='json',
    task_default_queue=settings.celery_task_default_queue,
    task_ignore_result=True,
    task_send_sent_event=True,
    task_serializer='json',
    task_track_started=True,
    timezone='UTC',
    worker_send_task_events=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule={
        'dispatch-due-reminders-every-minute': {
            'task': 'booking.notifications.process_pending_due_notifications',
            'schedule': 60.0,
            'args': (100,),
        },
    },
)
