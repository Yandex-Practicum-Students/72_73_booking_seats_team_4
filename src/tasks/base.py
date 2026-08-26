import asyncio
from functools import wraps
from typing import Any, Callable, Coroutine

from celery import Task
from celery.exceptions import Retry
from celery.signals import worker_process_init, worker_process_shutdown
from loguru import logger

_worker_loop: asyncio.AbstractEventLoop | None = None


@worker_process_init.connect
def init_worker_event_loop(**_: Any) -> None:
    """Инициализация единого Event Loop на весь жизненный цикл процесса воркера."""
    global _worker_loop
    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)


@worker_process_shutdown.connect
def shutdown_worker_event_loop(**_: Any) -> None:
    """Корректное закрытие Event Loop и очистка ресурсов при остановке процесса."""
    global _worker_loop
    if _worker_loop and not _worker_loop.is_closed():
        _worker_loop.run_until_complete(_worker_loop.shutdown_asyncgens())
        _worker_loop.close()
    _worker_loop = None


def get_worker_loop() -> asyncio.AbstractEventLoop:
    """Получение Event Loop."""
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def async_task(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Декоратор для исполнения async-функций в постоянном Event Loop воркера."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        loop = get_worker_loop()
        return loop.run_until_complete(func(*args, **kwargs))

    return wrapper


class RetryableTask(Task):
    """Базовый класс для Celery-задач с автоматическим retry и логированием."""

    abstract = True
    max_retries: int = 3
    default_countdown: int = 60
    no_retry_exceptions: tuple[type[Exception], ...] = ()

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Точка входа для выполнения задачи Celery."""
        log = logger.bind(task_name=self.name, task_id=self.request.id)
        log.info('Старт задачи {name}', name=self.name)

        try:
            return super().run(*args, **kwargs)
        except Retry:
            raise
        except Exception as error:
            if isinstance(error, self.no_retry_exceptions):
                log.error(
                    'Задача {id} -> {name} упала с ошибкой {error}, ретрай не применяется',
                    id=self.request.id,
                    name=self.name,
                    error=error,
                    exc_info=True,
                )
                raise error

            attempts = self.request.retries + 1
            if self.request.retries < self.max_retries:
                log.warning(
                    'Задача {id} -> {name} упала. Ретрай {attempts}/{max_retries}',
                    id=self.request.id,
                    name=self.name,
                    attempts=attempts,
                    max_retries=self.max_retries,
                    exc_info=True,
                )
                raise self.retry(countdown=self.default_countdown, exc=error)

            log.error(
                'Задача {id} -> {name} провалена после {attempts} попыток',
                id=self.request.id,
                name=self.name,
                attempts=self.max_retries,
                exc_info=True,
            )
            raise error
