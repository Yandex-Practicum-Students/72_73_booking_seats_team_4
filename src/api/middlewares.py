import time

from fastapi import status
from loguru import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LoggingContextMiddleware:
    """Добавляет HTTP-контекст к логам текущего запроса."""

    def __init__(self, app: ASGIApp) -> None:
        """При создании экземпляра посредника передаем объект нашего приложения."""
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Логика получения и трансляции данных запроса при вызове посредника."""
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        method = scope.get('method', '-')
        path = scope.get('path', '-')
        status_code: int | None = None
        started_at = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code

            if message['type'] == 'http.response.start':
                status_code = message['status']

            await send(message)

        with logger.contextualize(
            user_id='SYSTEM',
            username='SYSTEM',
            method=method,
            path=path,
        ):
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                logger.exception(
                    'Необработанное исключение при обработке запроса',
                )
                raise
            finally:
                duration_ms = (time.perf_counter() - started_at) * 1000
                logger.info(
                    'Отправлен HTTP-ответ: status_code={}, duration_ms={:.2f}',
                    status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
                    duration_ms,
                )
