import sys

from loguru import logger

LOG_FORMAT = (
    '{time:YYYY-MM-DD HH:mm:ss.SSS} | '
    '{level: <8} | '
    # '{extra[user_id]} - '
    # '{extra[username]} | '
    '{name} | '
    '{message}'
)


def configure_loguru() -> None:
    """Функция настройки параметров логгирования."""
    logger.remove()

    logger.add(sys.stdout, level='INFO', format=LOG_FORMAT, enqueue=True)

    logger.add(
        'logs/app.log',
        rotation='10 MB',
        retention=5,
        level='INFO',
        format=LOG_FORMAT,
        enqueue=True,
        encoding='utf-8',
    )
