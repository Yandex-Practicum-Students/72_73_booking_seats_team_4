from fastapi import APIRouter

from api import (
    cafe_router,
    dish_router,
    media_router,
    slots_router,
    tables_router,
    users_router,
)

api_router = APIRouter()

api_router.include_router(users_router)

api_router.include_router(
    cafe_router,
    prefix='/cafes',
    tags=['Кафе'],
)

api_router.include_router(
    tables_router,
    prefix='/cafes/{cafe_id}/tables',
    tags=['Столы'],
)

api_router.include_router(
    slots_router,
    prefix='/cafes/{cafe_id}/time_slots',
    tags=['Временные слоты'],
)

api_router.include_router(
    dish_router,
    prefix='/dishes',
    tags=['Блюда'],
)

api_router.include_router(
    media_router,
    prefix='/media',
    tags=['Изображения'],
)
