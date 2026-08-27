FROM python:3.12-alpine

SHELL ["/bin/sh", "-exc"]

RUN apk add --no-cache netcat-openbsd shadow


COPY --link --from=ghcr.io/astral-sh/uv:0.4 /uv /usr/local/bin/uv

ARG USER_ID=1000
ARG GROUP_ID=1000

RUN groupadd -g ${GROUP_ID} devuser \
    && useradd -u ${USER_ID} -g devuser -m -s /bin/sh devuser

ENV UV_PYTHON="python3.12" \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONOPTIMIZE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --chown=${USER_ID}:${GROUP_ID} pyproject.toml uv.lock entrypoint.sh /app/

USER devuser

RUN uv sync --no-dev --no-install-project --frozen && uv cache clean

ENV PATH=/app/.venv/bin:$PATH

COPY --chown=${USER_ID}:${GROUP_ID} ./src /app/src

EXPOSE 8000/tcp

ENTRYPOINT [ "/bin/sh", "entrypoint.sh" ]
