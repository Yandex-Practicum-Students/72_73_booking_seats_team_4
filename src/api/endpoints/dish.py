import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.dish import get_dish_or_404, require_manager_cafe_access_for_dish
from api.dependencies.permissions import CurrentUser, StaffUser
from api.responses import error_responses
from crud.dish import dish_crud
from models.dish import Dish
from models.user import UserRole
from schemas.dish import DishCreate, DishInfo, DishUpdate

from core.core_dependencies import redis_dep
from core.db import DBSession

GET_RESPONSES = (
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
)

POST_RESPONSES = (
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
)

PATCH_RESPONSES = (
    status.HTTP_400_BAD_REQUEST,
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
)

DELETE_RESPONSES = (
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT,
)

router = APIRouter()


@router.get(
    '',
    response_model=list[DishInfo],
    responses=error_responses(*GET_RESPONSES),
    summary='Список блюд',
)
async def get_all_dishes(
    current_user: CurrentUser,
    session: DBSession,
    show_active: Optional[bool] = Query(None),
    cafe_id: Optional[uuid.UUID] = Query(None),
) -> list[Dish]:
    """Получение списка блюд.

    Для администраторов - все блюда (учитываем параметр show_active),
    для менеджеров и пользователей - только активные.
    """
    if current_user.role != UserRole.ADMIN:
        show_active = True
    return await dish_crud.get_all(
        session=session,
        is_active=show_active,
        cafe_id=cafe_id,
    )


@router.post(
    '',
    response_model=DishInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(*POST_RESPONSES),
    summary='Создание нового блюда',
)
async def create_dish(
    dish_create: DishCreate,
    current_user: StaffUser,
    session: DBSession,
) -> Dish:
    """Создание нового блюда.

    Только для администраторов и менеджеров.
    """
    require_manager_cafe_access_for_dish(current_user, dish_create.cafes_id)
    return await dish_crud.create(dish_create, session)


@router.get(
    '/{dish_id}',
    response_model=DishInfo,
    responses=error_responses(*GET_RESPONSES),
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
    if current_user.role == UserRole.USER and not dish.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Блюдо не найдено',
        )

    return dish


@router.patch(
    '/{dish_id}',
    response_model=DishInfo,
    responses=error_responses(*PATCH_RESPONSES),
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
    require_manager_cafe_access_for_dish(current_user, [cafe.id for cafe in dish.cafes])
    return await dish_crud.update(dish, dish_update, session, redis)


@router.delete(
    '/{dish_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(*DELETE_RESPONSES),
    summary='Удаление блюда по его ID (мягкое удаление)',
)
async def delete_dish(
    dish_id: uuid.UUID,
    current_user: StaffUser,
    session: DBSession,
    dish: Dish = Depends(get_dish_or_404),
) -> None:
    """Мягкое удаление блюда (установка is_active=False).

    Только для администраторов и менеджеров.
    """
    require_manager_cafe_access_for_dish(current_user, [cafe.id for cafe in dish.cafes])
    await dish_crud.soft_delete(dish, session)
