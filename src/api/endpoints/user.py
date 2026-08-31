import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import (
    MeUser,
    StaffUser,
)
from api.responses import error_responses
from api.responses.statuses import (
    CREATED,
    LOGIN,
    LOGIN_DESCRIPTIONS,
    RESOURCE_DETAIL,
    RESOURCE_UPDATE,
    USER_CREATE,
    USER_LIST,
    USER_ME,
    USER_UPDATE_ME,
)
from api.validators import ensure_contact_remains, reject_null_required_fields
from crud.user import user_crud
from models.user import User, UserRole
from schemas.user import AuthData, AuthToken, UserCreate, UserInfo, UserUpdate
from services.user import ensure_user_update_allowed

from core.core_dependencies import redis_dep
from core.db import get_session
from core.user import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    register_access_token,
    verify_password,
)

router = APIRouter()
auth_router = APIRouter(prefix='/auth', tags=['Аутентификация'])
users_router = APIRouter(prefix='/users', tags=['Пользователи'])


@auth_router.post(
    '/login',
    response_model=AuthToken,
    responses=error_responses(
        *LOGIN,
        descriptions=LOGIN_DESCRIPTIONS,
    ),
    summary='Получение токена авторизации',
)
async def login(
    credentials: AuthData,
    redis: redis_dep,
    session: AsyncSession = Depends(get_session),
) -> AuthToken:
    """Аутентифицирует пользователя по email или телефону."""
    user = await user_crud.get_by_login(credentials.login, session)
    password = credentials.password.get_secret_value()

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
    else:
        verified, updated_hash = verify_password(password, user.hashed_password)
        if verified and user.is_active:
            if updated_hash is not None:
                user.hashed_password = updated_hash
                await session.commit()
            access_token = create_access_token(user.id)
            await register_access_token(access_token, redis)
            return AuthToken(
                access_token=access_token,
                token_type='bearer',
            )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail='Неверные имя пользователя или пароль.',
    )


@users_router.post(
    '',
    response_model=UserInfo,
    status_code=CREATED,
    responses=error_responses(*USER_CREATE),
    summary='Регистрация нового пользователя',
)
async def create_user(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Регистрирует пользователя с безопасным набором полномочий."""
    return await user_crud.create(user_create, session)


@users_router.get(
    '',
    response_model=list[UserInfo],
    responses=error_responses(*USER_LIST),
    summary='Получение списка пользователей',
)
async def get_all_users(
    _: StaffUser,
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    """Возвращает пользователей администратору или менеджеру."""
    return await user_crud.get_all(session)


@users_router.get(
    '/me',
    response_model=UserInfo,
    responses=error_responses(*USER_ME),
    summary='Получение информации о текущем пользователе',
)
async def get_me(user: MeUser) -> User:
    """Возвращает данные текущего активного пользователя."""
    return user


@users_router.patch(
    '/me',
    response_model=UserInfo,
    responses=error_responses(*USER_UPDATE_ME),
    summary='Обновление информации о текущем пользователе',
)
async def update_me(
    user_update: UserUpdate,
    user: MeUser,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Изменяет доступные пользователю поля собственной записи."""
    update_data = user_update.model_dump(
        exclude_unset=True,
        exclude={'is_active', 'role'},
    )
    reject_null_required_fields(update_data)
    ensure_contact_remains(user, update_data)
    return await user_crud.update(user, update_data, session)


@users_router.get(
    '/{user_id}',
    response_model=UserInfo,
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Получение информации о пользователе по его ID',
)
async def get_user_by_id(
    user_id: uuid.UUID,
    _: StaffUser,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Возвращает пользователя администратору или менеджеру."""
    return await user_crud.get_or_raise(user_id, session)


@users_router.patch(
    '/{user_id}',
    response_model=UserInfo,
    responses=error_responses(*RESOURCE_UPDATE),
    summary='Обновление информации о пользователе по его ID',
)
async def update_user_by_id(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    actor: StaffUser,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Изменяет пользователя с учётом полномочий менеджера."""
    target_user = await user_crud.get_or_raise(user_id, session)
    update_data = user_update.model_dump(exclude_unset=True)
    reject_null_required_fields(update_data)
    requested_role = update_data.get('role')
    ensure_user_update_allowed(actor, target_user, requested_role)
    if requested_role is not None and requested_role != UserRole.MANAGER:
        target_user.cafe_id = None

    ensure_contact_remains(target_user, update_data)
    return await user_crud.update(target_user, update_data, session)


router.include_router(auth_router)
router.include_router(users_router)
