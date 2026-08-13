from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

from api.endpoints.user import router as user_router

from core.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Жизненный цикл приложения FastAPI."""
    # TODO: Добавить код, выполняемый при старте приложения
    yield
    # TODO: Добавить код, выполняемый при остановке приложения


app = FastAPI(
    title=settings.title,
    version=settings.version,
    description=settings.description,
)
app.include_router(user_router)


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
    uvicorn.run(app, host='0.0.0.0', port=8000)
