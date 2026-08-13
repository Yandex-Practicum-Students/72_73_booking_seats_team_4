import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.user import UserAlreadyExistsError, UserCRUD
from models.user import User
from schemas.user import AuthData, AuthToken, UserCreate, UserInfo, UserUpdate

from core.db import get_session
from core.user import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    get_current_user,
    verify_password,
)

router = APIRouter()
auth_router = APIRouter(prefix='/auth', tags=['Аутентификация'])
users_router = APIRouter(prefix='/users', tags=['Пользователи'])

CurrentUser = Annotated[User, Depends(get_current_user)]


def _role_name(user: User) -> str:
    """Возвращает нормализованное имя роли пользователя."""
    role = getattr(user, 'role', None)
    return str(getattr(role, 'value', role) or '').upper()


def _is_admin(user: User) -> bool:
    """Проверяет административные полномочия пользователя."""
    return _role_name(user) == 'ADMIN'


async def get_staff_user(user: CurrentUser) -> User:
    """Разрешает доступ администраторам и менеджерам."""
    if _is_admin(user) or _role_name(user) == 'MANAGER':
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Доступ запрещён.',
    )


async def get_admin_user(user: CurrentUser) -> User:
    """Разрешает доступ только администраторам."""
    if _is_admin(user):
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail='Доступ запрещён.',
    )


async def _get_user_or_404(user_id: uuid.UUID, crud: UserCRUD) -> User:
    """Возвращает пользователя либо ответ 404."""
    user = await crud.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Пользователь не найден.',
        )
    return user


def _ensure_contact_remains(user: User, update_data: dict[str, object]) -> None:
    """Не позволяет удалить оба доступных идентификатора для входа."""
    email = update_data.get('email', user.email)
    phone = update_data.get('phone', user.phone)
    if not email and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Необходимо указать email или телефон.',
        )


def _reject_null_required_fields(update_data: dict[str, object]) -> None:
    """Не позволяет обнулить обязательные поля через PATCH."""
    null_fields = {
        field_name
        for field_name in ('username', 'role', 'is_active')
        if field_name in update_data and update_data[field_name] is None
    }
    if null_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Поля {", ".join(sorted(null_fields))} не могут быть null.',
        )


def _user_conflict_error() -> HTTPException:
    """Формирует единый ответ при конфликте уникальных полей."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Пользователь с такими данными уже существует.',
    )


@auth_router.post(
    '/login',
    response_model=AuthToken,
    summary='Получение токена авторизации',
)
async def login(
    credentials: AuthData,
    session: AsyncSession = Depends(get_session),
) -> AuthToken:
    """Аутентифицирует пользователя по email или телефону."""
    crud = UserCRUD(session)
    user = await crud.get_by_login(credentials.login)
    password = credentials.password.get_secret_value()

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
    else:
        verified, updated_hash = verify_password(password, user.hashed_password)
        if verified and user.is_active:
            if updated_hash is not None:
                user.hashed_password = updated_hash
                await session.flush()
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
    summary='Регистрация нового пользователя',
)
async def create_user(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Регистрирует пользователя с безопасным набором полномочий."""
    try:
        return await UserCRUD(session).create(user_create)
    except UserAlreadyExistsError as error:
        raise _user_conflict_error() from error


@users_router.get(
    '',
    response_model=list[UserInfo],
    summary='Получение списка пользователей',
)
async def get_all_users(
    _: Annotated[User, Depends(get_staff_user)],
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    """Возвращает пользователей администратору или менеджеру."""
    return await UserCRUD(session).get_all()


@users_router.get(
    '/me',
    response_model=UserInfo,
    summary='Получение информации о текущем пользователе',
)
async def get_me(user: CurrentUser) -> User:
    """Возвращает данные текущего активного пользователя."""
    return user


@users_router.patch(
    '/me',
    response_model=UserInfo,
    summary='Обновление информации о текущем пользователе',
)
async def update_me(
    user_update: UserUpdate,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Изменяет доступные пользователю поля собственной записи."""
    update_data = user_update.model_dump(
        exclude_unset=True,
        exclude={'is_active', 'role'},
    )
    _reject_null_required_fields(update_data)
    _ensure_contact_remains(user, update_data)
    try:
        return await UserCRUD(session).update(user, update_data)
    except UserAlreadyExistsError as error:
        raise _user_conflict_error() from error


@users_router.get(
    '/{user_id}',
    response_model=UserInfo,
    summary='Получение информации о пользователе по его ID',
)
async def get_user_by_id(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(get_staff_user)],
    session: AsyncSession = Depends(get_session),
) -> User:
    """Возвращает пользователя администратору или менеджеру."""
    return await _get_user_or_404(user_id, UserCRUD(session))


@users_router.patch(
    '/{user_id}',
    response_model=UserInfo,
    summary='Обновление информации о пользователе по его ID',
)
async def update_user_by_id(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    actor: Annotated[User, Depends(get_staff_user)],
    session: AsyncSession = Depends(get_session),
) -> User:
    """Изменяет пользователя с учётом полномочий менеджера."""
    crud = UserCRUD(session)
    target_user = await _get_user_or_404(user_id, crud)
    update_data = user_update.model_dump(exclude_unset=True)
    _reject_null_required_fields(update_data)
    requested_role = update_data.get('role')
    requested_role_name = str(
        getattr(requested_role, 'value', requested_role) or '',
    ).upper()
    if not _is_admin(actor) and (_is_admin(target_user) or requested_role_name == 'ADMIN'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Менеджер не может изменять администратора или назначать эту роль.',
        )
    if requested_role is not None and requested_role_name != 'MANAGER':
        target_user.cafe_id = None

    _ensure_contact_remains(target_user, update_data)
    try:
        return await crud.update(target_user, update_data)
    except UserAlreadyExistsError as error:
        raise _user_conflict_error() from error


@users_router.delete(
    '/{user_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Удаление пользователя по его ID',
)
async def delete_user_by_id(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(get_admin_user)],
    session: AsyncSession = Depends(get_session),
) -> None:
    """Блокирует пользователя; операция доступна только администратору."""
    crud = UserCRUD(session)
    user = await _get_user_or_404(user_id, crud)
    await crud.soft_delete(user)


router.include_router(auth_router)
router.include_router(users_router)
