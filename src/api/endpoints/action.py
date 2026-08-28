import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.action import get_action_or_404
from api.dependencies.permissions import CurrentUser, StaffUser
from api.responses import error_responses
from crud.action import action_crud
from models.action import Action
from models.user import UserRole
from schemas.action import ActionCreate, ActionInfo, ActionUpdate
from services.action import ensure_cafes_exist, ensure_manager_cafe_access

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

router = APIRouter()


@router.get(
    '',
    response_model=list[ActionInfo],
    responses=error_responses(*GET_RESPONSES),
    summary='Список акций',
)
async def get_all_actions(
    current_user: CurrentUser,
    session: DBSession,
    show_active: Optional[bool] = Query(None),
    cafe_id: Optional[uuid.UUID] = Query(None),
) -> list[Action]:
    """Получение списка акций.

    Для администраторов - все акции (учитываем параметр show_active),
    для менеджеров и пользователей - только активные.
    """
    if current_user.role != UserRole.ADMIN:
        show_active = True

    # Менеджер видит только акции своего кафе
    effective_cafe_id = cafe_id
    if current_user.role == UserRole.MANAGER:
        effective_cafe_id = current_user.cafe_id

    return await action_crud.get_all(
        session=session,
        is_active=show_active,
        cafe_id=effective_cafe_id,
    )


@router.post(
    '',
    response_model=ActionInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(*POST_RESPONSES),
    summary='Создание новой акции',
)
async def create_action(
    action_create: ActionCreate,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
) -> Action:
    """Создание новой акции.

    Только для администраторов и менеджеров.
    """
    ensure_manager_cafe_access(current_user, action_create.cafes_id)
    await ensure_cafes_exist(action_create.cafes_id, session)
    return await action_crud.create(action_create, session, redis)


@router.get(
    '/{action_id}',
    response_model=ActionInfo,
    responses=error_responses(*GET_RESPONSES),
    summary='Информация об акции по её ID',
)
async def get_action_by_id(
    action_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    action: Action = Depends(get_action_or_404),
) -> Action:
    """Получение информации об акции по её ID.

    Для администраторов и менеджеров - все акции,
    для пользователей - только активные.
    """
    if current_user.role == UserRole.USER and not action.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Акция не найдена',
        )

    return action


@router.patch(
    '/{action_id}',
    response_model=ActionInfo,
    responses=error_responses(*PATCH_RESPONSES),
    summary='Обновление информации об акции по её ID',
)
async def update_action(
    action_id: uuid.UUID,
    action_update: ActionUpdate,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
    action: Action = Depends(get_action_or_404),
) -> Action:
    """Обновление информации об акции по её ID.

    Только для администраторов и менеджеров.
    """
    new_cafes_id = (
        action_update.cafes_id
        if action_update.cafes_id is not None
        else [cafe.id for cafe in action.cafes]
    )
    ensure_manager_cafe_access(current_user, new_cafes_id)
    await ensure_cafes_exist(new_cafes_id, session)
    return await action_crud.update(action, action_update, session, redis)


@router.delete(
    '/{action_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(*GET_RESPONSES),
    summary='Удаление акции по её ID (мягкое удаление)',
)
async def delete_action(
    action_id: uuid.UUID,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
    action: Action = Depends(get_action_or_404),
) -> None:
    """Мягкое удаление акции (установка is_active=False).

    Только для администраторов и менеджеров.
    """
    ensure_manager_cafe_access(current_user, [cafe.id for cafe in action.cafes])
    await action_crud.soft_delete(action, session, redis)
