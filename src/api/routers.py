from fastapi import APIRouter

from api import (
    action_router,
    booking_router,
    cafe_router,
    dish_router,
    media_router,
    slots_router,
    tables_router,
    users_router,
)

from core.settings import settings

v1_api_router = APIRouter(prefix=settings.api_v1_prefix)

v1_api_router.include_router(users_router)

v1_api_router.include_router(
    action_router,
    prefix='/actions',
    tags=['Акции'],
)

v1_api_router.include_router(
    cafe_router,
    prefix='/cafes',
    tags=['Кафе'],
)

v1_api_router.include_router(
    booking_router,
    prefix='/booking',
    tags=['Бронирования'],
)

v1_api_router.include_router(
    tables_router,
    prefix='/cafes/{cafe_id}/tables',
    tags=['Столы'],
)

v1_api_router.include_router(
    slots_router,
    prefix='/cafes/{cafe_id}/time_slots',
    tags=['Временные слоты'],
)

v1_api_router.include_router(
    dish_router,
    prefix='/dishes',
    tags=['Блюда'],
)

v1_api_router.include_router(
    media_router,
    prefix='/media',
    tags=['Изображения'],
)
