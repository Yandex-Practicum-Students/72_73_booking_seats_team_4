import logging
import sys

from loguru import logger

from core.settings import Environment, settings

PROD_LOG_FORMAT = (
    '{time:YYYY-MM-DD HH:mm:ss} | '
    '{level: <8} | '
    'user_id={extra[user_id]} | '
    'username={extra[username]} | '
    '{name}:{function}:{line} | '
    '{message}'
)

DEV_LOG_FORMAT = (
    '<dim>{time:YYYY-MM-DD HH:mm:ss.SSS} | </>'
    '<level>{level: <8} | </>'
    'user_id={extra[user_id]} | '
    'username={extra[username]} | '
    '<cyan>{name}.</>'
    '{function}:{line}'
)

logger.configure(
    extra={
        'user_id': 'SYSTEM',
        'username': 'SYSTEM',
    },
)


class InterceptHandler(logging.Handler):
    """Обработчик перехвата записей logging в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Перенаправить запись стандартного logging в loguru.

        Метод вызывается модулем logging для каждой записи, прошедшей через
        настроенные handlers.

        - Определяет уровень логирования, совместимый с loguru.
        - Находит в стеке вызовов первый фрейм за пределами модуля logging,
          чтобы loguru корректно указал файл, строку и функцию источника лога.
        - Передаёт в loguru текст сообщения и информацию об исключении (если есть).

        Примечания:
        ----------
        - Если уровень из record.levelname неизвестен loguru, используется
          числовое значение record.levelno.
        - Обход стека нужен, чтобы в выводе loguru источником лога отображалось
          место вызова logging.info()/warning()/error() в пользовательском коде,
          а не внутренности модуля logging или этого хендлера.
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 0

        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(
            depth=depth,
            exception=record.exc_info,
        ).log(
            level,
            record.getMessage(),
        )


def configure_stdlib_logging() -> None:
    """Перенаправить записи стандартного logging и Uvicorn в loguru.

    Функция настраивает интеграцию между модулем logging из стандартной
    библиотеки Python и loguru:

    - Создаёт единый экземляр InterceptHandler, который пересылает записи logging
      в loguru.logger.
    - Для корневого логгера ('') и логгеров Uvicorn ('uvicorn',
      'uvicorn.access', 'uvicorn.error'):
        * заменяет все существующие handlers на InterceptHandler;
        * устанавливает уровень логирования в NOTSET, чтобы не фильтровать
          записи на уровне логгера;
        * для дочерних логгеров Uvicorn отключает propagate, чтобы избежать
          дублирования записей через родительские логгеры.

    В результате все сообщения, отправленные через logging а также
    встроенные логи Uvicorn, выводятся через loguru с корректными уровнями,
    именами модулей, номерами строк и трейсбэком.

    Примечания:
    ----------
    - Функция должна вызываться один раз при старте приложения, до начала
      активной работы с логированием.
    - При запуске приложения через uvicorn деактивируем конфигурацию из коробки:
      uvicorn.run(app, host=..., port=..., log_config=None).
    """
    intercept_handler = InterceptHandler()

    for logger_name in ('', 'uvicorn', 'uvicorn.access', 'uvicorn.error'):
        stdlib_logger = logging.getLogger(logger_name)
        stdlib_logger.handlers = [intercept_handler]
        stdlib_logger.setLevel(logging.NOTSET)

        if logger_name:
            stdlib_logger.propagate = False


def configure_loguru() -> None:
    """Настройка конфигурации логирования.

    Примечания:
    ------
    - И в dev, и в prod логи пишутся:
        * в консоль (stdout)
        * в файл (settings.log_file_path)
    - Уровень логирования для обоих выходов берётся из settings.log_level.
    - Разница между dev и prod:
        * формат вывода (подробный с переменными vs минималистичный без переменных)
        * diagnose - показ переменных в логах - включен в dev, выключен в prod)
    """
    logger.remove()

    is_production = settings.environment == Environment.PRODUCTION

    log_format = DEV_LOG_FORMAT if not is_production else PROD_LOG_FORMAT

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=log_format,
        enqueue=True,
        diagnose=not is_production,
    )

    logger.add(
        settings.log_file_path,
        level=settings.log_level,
        rotation=f'{settings.log_rotation_size_mb} MB',
        retention=settings.log_retention_count,
        format=log_format,
        enqueue=True,
        diagnose=not is_production,
    )

    configure_stdlib_logging()
