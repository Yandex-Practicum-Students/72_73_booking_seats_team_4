import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies.dish import get_dish_or_404
from api.dependencies.filters import Boolean, filter_user_role_manager_for_cafe_id, resolve_show_active
from api.dependencies.permissions import CurrentUser, StaffUser, ensure_active_resource_visible
from api.responses import error_responses
from api.responses.statuses import CREATED, RESOURCE_CREATE, RESOURCE_DETAIL, RESOURCE_UPDATE
from crud.dish import dish_crud
from models.dish import Dish
from schemas.dish import DishCreate, DishInfo, DishUpdate
from services.dish import create_dish as create_dish_service
from services.dish import update_dish as update_dish_service

from core.db import DBSession
from core.redis import redis_dep

router = APIRouter()


@router.get(
    '',
    response_model=list[DishInfo],
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Список блюд',
)
async def get_all_dishes(
    current_user: CurrentUser,
    session: DBSession,
    show_active: Boolean = None,
    cafe_id: Optional[uuid.UUID] = Query(None),
) -> list[Dish]:
    """Получение списка блюд.

    Для администраторов - все блюда (учитываем параметр show_active),
    для менеджеров и пользователей - только активные.
    """
    show_active = resolve_show_active(current_user, show_active)
    cafe_id = filter_user_role_manager_for_cafe_id(current_user, cafe_id)

    return await dish_crud.get_all(
        session=session,
        is_active=show_active,
        cafe_id=cafe_id,
    )


@router.post(
    '',
    response_model=DishInfo,
    status_code=CREATED,
    responses=error_responses(*RESOURCE_CREATE),
    summary='Создание нового блюда',
)
async def create_dish(
    dish_create: DishCreate,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
) -> Dish:
    """Создание нового блюда.

    Только для администраторов и менеджеров.
    """
    return await create_dish_service(dish_create, current_user, session, redis)


@router.get(
    '/{dish_id}',
    response_model=DishInfo,
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Информация о блюде по его ID',
)
async def get_dish_by_id(
    dish_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    dish: Dish = Depends(get_dish_or_404),
) -> Dish:
    """Получение информации о блюде по его ID.

    Для администраторов и менеджеров - все блюда,
    для пользователей - только активные.
    """
    ensure_active_resource_visible(current_user, dish, 'Блюдо не найдено')

    return dish


@router.patch(
    '/{dish_id}',
    response_model=DishInfo,
    responses=error_responses(*RESOURCE_UPDATE),
    summary='Обновление информации о блюде по его ID',
)
async def update_dish(
    dish_id: uuid.UUID,
    dish_update: DishUpdate,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
    dish: Dish = Depends(get_dish_or_404),
) -> Dish:
    """Обновление информации о блюде по его ID.

    Только для администраторов и менеджеров.
    """
    return await update_dish_service(dish, dish_update, current_user, session, redis)
