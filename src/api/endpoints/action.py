import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies.action import get_action_or_404
from api.dependencies.filters import Boolean, resolve_show_active
from api.dependencies.permissions import CurrentUser, StaffUser, ensure_active_resource_visible
from api.responses import error_responses
from api.responses.statuses import CREATED, RESOURCE_CREATE, RESOURCE_DETAIL, RESOURCE_UPDATE
from crud.action import action_crud
from models.action import Action
from models.user import UserRole
from schemas.action import ActionCreate, ActionInfo, ActionUpdate
from services.action import create_action as create_action_service
from services.action import update_action as update_action_service

from core.core_dependencies import redis_dep
from core.db import DBSession

router = APIRouter()


@router.get(
    '',
    response_model=list[ActionInfo],
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Список акций',
)
async def get_all_actions(
    current_user: CurrentUser,
    session: DBSession,
    show_active: Boolean = None,
    cafe_id: Optional[uuid.UUID] = Query(None),
) -> list[Action]:
    """Получение списка акций с учётом роли пользователя."""
    effective_cafe_id = cafe_id
    show_active = resolve_show_active(
        current_user,
        show_active,
        manager_can_filter=True,
    )
    if current_user.role == UserRole.MANAGER:
        if current_user.cafe_id is None:
            return []
        effective_cafe_id = current_user.cafe_id

    return await action_crud.get_all(
        session=session,
        is_active=show_active,
        cafe_id=effective_cafe_id,
    )


@router.post(
    '',
    response_model=ActionInfo,
    status_code=CREATED,
    responses=error_responses(*RESOURCE_CREATE),
    summary='Создание новой акции',
)
async def create_action(
    action_create: ActionCreate,
    current_user: StaffUser,
    session: DBSession,
    redis: redis_dep,
) -> Action:
    """Создание акции администратором или менеджером."""
    return await create_action_service(action_create, current_user, session, redis)


@router.get(
    '/{action_id}',
    response_model=ActionInfo,
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Информация об акции по её ID',
)
async def get_action_by_id(
    action_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    action: Action = Depends(get_action_or_404),
) -> Action:
    """Получение акции по ID с проверкой её доступности пользователю."""
    ensure_active_resource_visible(current_user, action, 'Акция не найдена')
    return action


@router.patch(
    '/{action_id}',
    response_model=ActionInfo,
    responses=error_responses(*RESOURCE_UPDATE),
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
    """Обновление акции администратором или менеджером."""
    return await update_action_service(action, action_update, current_user, session, redis)
