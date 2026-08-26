from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import APIError
from api.exceptions import (
    api_error_handler,
    dish_already_exists_handler,
    http_exception_handler,
    manager_already_assigned_handler,
    manager_not_found_handler,
    manager_role_error_handler,
    request_validation_error_handler,
    user_already_exists_handler,
    user_not_found_handler,
)
from api.routers import api_router
from crud.cafe import ManagerAlreadyAssignedError, ManagerNotFoundError, ManagerRoleError
from crud.dish import DishAlreadyExistsError
from crud.user import UserAlreadyExistsError, UserNotFoundError

from core.logging import configure_loguru
from core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Жизненный цикл приложения FastAPI."""
    logger.info('Привет! Запускаем приложение...')
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=settings.decode_responses,
        max_connections=settings.max_connections,
        password=settings.redis_password,
    )
    try:
        await app.state.redis.ping()
        logger.info('Успешное подключение к пулу Redis!')
    except Exception as e:
        logger.error(f'Не удалось подключиться к Redis: {e}')
    yield
    logger.info('Закрываем соединения с Redis...')
    await app.state.redis.close()
    logger.info('Завершаем работу приложения. До скорых встреч!')


configure_loguru()

app = FastAPI(
    title=settings.title,
    version=settings.version,
    description=settings.description,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_hosts,
    allow_credentials=settings.allow_credentials,
    allow_methods=settings.allowed_methods,
    allow_headers=settings.allowed_headers,
)

app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(DishAlreadyExistsError, dish_already_exists_handler)
app.add_exception_handler(UserAlreadyExistsError, user_already_exists_handler)
app.add_exception_handler(UserNotFoundError, user_not_found_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(ManagerNotFoundError, manager_not_found_handler)
app.add_exception_handler(ManagerRoleError, manager_role_error_handler)
app.add_exception_handler(ManagerAlreadyAssignedError, manager_already_assigned_handler)
app.include_router(api_router)


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
