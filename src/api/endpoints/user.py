import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import (
    AdminUser,
    MeUser,
    StaffUser,
    ensure_user_update_allowed,
)
from api.responses import error_responses
from api.validators import ensure_contact_remains, reject_null_required_fields
from crud.user import user_crud
from models.user import User, UserRole
from schemas.user import AuthData, AuthToken, UserCreate, UserInfo, UserUpdate

from core.db import get_session
from core.user import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    verify_password,
)

router = APIRouter()
auth_router = APIRouter(prefix='/auth', tags=['Аутентификация'])
users_router = APIRouter(prefix='/users', tags=['Пользователи'])


@auth_router.post(
    '/login',
    response_model=AuthToken,
    responses=error_responses(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        descriptions={
            status.HTTP_422_UNPROCESSABLE_CONTENT: 'Неверные имя пользователя или пароль',
        },
    ),
    summary='Получение токена авторизации',
)
async def login(
    credentials: AuthData,
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
            return AuthToken(
                access_token=create_access_token(user.id),
                token_type='bearer',
            )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail='Неверные имя пользователя или пароль.',
    )


@users_router.post(
    '',
    response_model=UserInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
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
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
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
    responses=error_responses(status.HTTP_403_FORBIDDEN),
    summary='Получение информации о текущем пользователе',
)
async def get_me(user: MeUser) -> User:
    """Возвращает данные текущего активного пользователя."""
    return user


@users_router.patch(
    '/me',
    response_model=UserInfo,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
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
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
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
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
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


@users_router.delete(
    '/{user_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Удаление пользователя по его ID',
)
async def delete_user_by_id(
    user_id: uuid.UUID,
    _: AdminUser,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Блокирует пользователя; операция доступна только администратору."""
    user = await user_crud.get_or_raise(user_id, session)
    await user_crud.soft_delete(user, session)


router.include_router(auth_router)
router.include_router(users_router)
