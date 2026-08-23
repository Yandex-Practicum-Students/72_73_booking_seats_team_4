import uuid
from typing import Optional
from venv import logger

from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api.dependencies.permissions import CurrentUser, StaffUser
from api.dependencies.tables import get_cafe_or_404, require_manager_cafe_access
from api.responses import error_responses
from crud.cafe import cafe_crud
from models import Cafe
from models.user import UserRole
from schemas.cafe import CafeCreate, CafeInfo, CafeUpdate

from core.db import DBSession

router = APIRouter()


@router.get(
    '',
    response_model=list[CafeInfo],
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Получение списка кафе',
)
async def get_cafes(
    current_user: CurrentUser,
    session: DBSession,
    show_active: Optional[bool] = Query(None,),
) -> list[Cafe]:
    """Получение списка кафе.

    Для администраторов и менеджеров - все кафе (с возможностью выбора),
    для пользователей - только активные.
    """
    try:
        if current_user.role == UserRole.ADMIN:
            cafes = await cafe_crud.get_all(
                session=session,
                show_active=show_active,
            )
        else:
            cafes = await cafe_crud.get_all(
                session=session,
                show_active=True,
            )

        # Явно преобразуем каждое кафе в Pydantic-схему
        result = []
        for cafe in cafes:
            # Гарантируем, что managers - это список
            if cafe.managers is None:
                cafe.managers = []
            else:
                cafe.managers = list(cafe.managers)

            # Преобразуем в Pydantic-схему
            cafe_info = CafeInfo.model_validate(cafe)
            result.append(cafe_info)

        return result

    except Exception as e:
        logger.error(f'Ошибка при получении списка кафе: {e}', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Ошибка при получении списка кафе: {str(e)}',
        )


@router.get(
    '/{cafe_id}',
    response_model=CafeInfo,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Получение информации о кафе по его ID',
)
async def get_cafe_by_id(
    cafe_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> Cafe:
    """Получение информации о кафе по его ID.

    Для администраторов и менеджеров - все кафе,
    для пользователей - только активные.
    """
    if current_user.role == UserRole.USER and not cafe.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кафе не найдено',
        )

    # Гарантируем, что managers - это список (даже если пустой)
    if cafe.managers is None:
        cafe.managers = []
    return cafe


@router.post(
    '',
    response_model=CafeInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Создание нового кафе',
)
async def create_cafe(
    cafe_create: CafeCreate,
    _: StaffUser,
    session: DBSession,
) -> Cafe:
    """Создает новое кафе.

    Только для администраторов и менеджеров.
    """
    return await cafe_crud.create(cafe_create, session)


@router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Обновление информации о кафе по его ID',
)
async def update_cafe(
    cafe_id: uuid.UUID,
    cafe_update: CafeUpdate,
    current_user: StaffUser,
    session: DBSession,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> Cafe:
    """Обновление информации о кафе по его ID.

    Только для администраторов и менеджеров.
    """
    """
    require_manager_cafe_access(current_user, cafe_id)
    return await cafe_crud.update(cafe, cafe_update, session)
    """
    try:
        return await cafe_crud.update(cafe, cafe_update, session)

    except ValueError as e:
        # Ошибка валидации (например, пользователи не найдены)
        logger.error(f'Ошибка валидации при обновлении кафе {cafe_id}: {e}')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except IntegrityError as e:
        # Ошибка целостности БД (например, дубликат имени/телефона)
        logger.error(f'Ошибка целостности БД при обновлении кафе {cafe_id}: {e}')
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Нарушение целостности данных. Проверьте уникальность полей (имя, адрес, телефон).',
        )

    except SQLAlchemyError as e:
        # Другие ошибки БД
        logger.error(f'Ошибка БД при обновлении кафе {cafe_id}: {e}', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Ошибка при работе с базой данных',
        )

    except Exception as e:
        # Непредвиденная ошибка
        logger.error(f'Непредвиденная ошибка при обновлении кафе {cafe_id}: {e}', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Внутренняя ошибка сервера',
        )

@router.delete(
    '/{cafe_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Удаление кафе по его ID (мягкое удаление)',
    include_in_schema=False,
)
async def delete_cafe(
    cafe_id: uuid.UUID,
    _: StaffUser,
    session: DBSession,
    cafe: Cafe = Depends(get_cafe_or_404),
) -> None:
    """Мягкое удаление кафе (установка is_active=False).

    Только для администраторов и менеджеров.
    """
    require_manager_cafe_access(_, cafe_id)
    await cafe_crud.soft_delete(cafe, session)
