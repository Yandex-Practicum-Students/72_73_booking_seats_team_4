FROM python:3.12-slim

SHELL ["/bin/sh", "-exc"]

RUN apt-get update && apt-get upgrade -y && apt-get install --quiet --no-install-recommends --assume-yes netcat-traditional

COPY --link --from=ghcr.io/astral-sh/uv:0.4 /uv /usr/local/bin/uv

ARG USER_ID=1000
ARG GROUP_ID=1000

RUN groupadd -g ${GROUP_ID} devuser \
    && useradd -u ${USER_ID} -g devuser -m -s /bin/bash devuser

USER devuser

# Задаём переменные окружения.
# UV_PYTHON — фиксирует версию Python.
# UV_PYTHON_DOWNLOADS — отключает автоматическую загрузку отсутствующих версий Python.
# UV_LINK_MODE — меняет способ установки пакетов из глобального кэша.
#   Вместо создания жёстких ссылок, файлы пакета копируются в директорию  виртуального окружения `site-packages`.
# UV_COMPILE_BYTECODE — включает компиляцию файлов Python в байт-код после установки.
# PYTHONOPTIMIZE — убирает инструкции `assert` и код, зависящий от значения  константы `__debug__`,
#   при компиляции файлов Python в байт-код.

ENV UV_PYTHON="python3.12" \
  UV_PYTHON_DOWNLOADS=never \
  UV_LINK_MODE=copy \
  UV_COMPILE_BYTECODE=1 \
  PYTHONOPTIMIZE=1

WORKDIR /app

COPY --chown=$USER_ID:$GROUP_ID pyproject.toml uv.lock entrypoint.sh /app/

RUN uv sync --no-dev --no-install-project --frozen

# PYTHONOPTIMIZE — указывает интерпретатору Python, что нужно использовать ранее скомпилированные файлы из  директории `__pycache__` с  суффиксом `opt-1` в имени.
# PYTHONFAULTHANDLER — устанавливает обработчики ошибок для дополнительных сигналов.
# PYTHONUNBUFFERED — отключает буферизацию для потоков stdout и stderr.

ENV PATH=/app/.venv/bin:$PATH \
  PYTHONOPTIMIZE=1 \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1

COPY --chown=$USER_ID:$GROUP_ID ./src /app

EXPOSE 8000/tcp

# ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
ENTRYPOINT [ "/bin/sh", "entrypoint.sh" ]
