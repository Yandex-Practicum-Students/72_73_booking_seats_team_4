import sys

from loguru import logger


def configure_loguru() -> None:
    """Функция настройки параметров логгирования."""
    logger.remove()

    logger.add(
        sys.stdout,
        level='INFO',
        format='{time:YYYY-MM-DD HH:mm:ss.SSS} | '
        '{level} | '
        # '{extra[user_id]} - '
        # '{extra[username]} | '
        '{name} | '
        '{message}',
        enqueue=True,
    )

    logger.add(
        'logs/app.log',
        level='INFO',
        format='{time:YYYY-MM-DD HH:mm:ss.SSS} | '
        '{level} | '
        # '{extra[user_id]} - '
        # '{extra[username]} | '
        '{name} | '
        '{message}',
        enqueue=True,
    )
