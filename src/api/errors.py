from collections.abc import Mapping


class APIError(Exception):
    """Ошибка API с явным кодом и сообщением для клиента."""

    def __init__(
        self,
        status_code: int,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Сохраняет HTTP-код, сообщение и необязательные заголовки."""
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.headers = headers
