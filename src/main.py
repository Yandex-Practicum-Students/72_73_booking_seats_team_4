from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.endpoints.cafe import cafe_router
from api.endpoints.slots import slots_router
from api.endpoints.tables import table_router
from api.endpoints.user import router as user_router
from api.errors import APIError
from api.exceptions import (
    api_error_handler,
    http_exception_handler,
    request_validation_error_handler,
    user_already_exists_handler,
    user_not_found_handler,
)
from crud.user import UserAlreadyExistsError, UserNotFoundError

from core.logging import configure_loguru
from core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Жизненный цикл приложения FastAPI."""
    logger.info('Привет! Запускаем приложение...')
    yield
    logger.info('Завершаем работу приложения. До скорых встреч!')


configure_loguru()

app = FastAPI(
    title=settings.title,
    version=settings.version,
    description=settings.description,
    lifespan=lifespan,
)
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(UserAlreadyExistsError, user_already_exists_handler)
app.add_exception_handler(UserNotFoundError, user_not_found_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)

app.include_router(user_router)
app.include_router(cafe_router)
app.include_router(table_router)
app.include_router(slots_router)


@app.get(
    path='/',
    response_model=dict,
)
async def index() -> dict:
    """Основная страница."""
    return {
        'app': f'{settings.title} ({settings.version})',
        'description': settings.description,
        'status': 'OK',
    }


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000, log_config=None)
