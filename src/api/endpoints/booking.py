import uuid

from fastapi import APIRouter
from loguru import logger

from api.dependencies.filters import Boolean, resolve_show_active
from api.dependencies.permissions import CurrentUser
from api.responses import error_responses
from api.responses.statuses import (
    BOOKING_CREATE,
    BOOKING_LIST,
    CREATED,
    OK,
    RESOURCE_DETAIL,
    RESOURCE_UPDATE,
)
from crud.booking import booking_crud
from models.booking import Booking
from models.user import UserRole
from schemas.booking import BookingCreate, BookingInfo, BookingUpdate
from services.booking import FilterParam
from services.dependencies import BookingServiceDep
from tasks.notifications import send_booking_notification

from core.db import DBSession

router = APIRouter()


@router.get(
    '',
    response_model=list[BookingInfo],
    status_code=OK,
    responses=error_responses(*BOOKING_LIST),
    summary='Получение списка бронирований',
)
async def get_all_bookings(
    current_user: CurrentUser,
    session: DBSession,
    filters: FilterParam,
    show_active: Boolean = None,
) -> list[Booking]:
    """Получение списка бронирований.

    Для администраторов - все бронирования (с возможностью выбора).
    Для менеджера - все активные бронирования своего кафе (с возможностью выбора).
    Для пользователей - только свои активные бронирования(параметры игнорируются, кроме ID кафе).
    """
    logger.info('Фильтрует параметры в зависимости от роли пользователя для получения списка бронирований.')
    show_active = resolve_show_active(
        current_user,
        show_active,
        manager_can_filter=True,
    )
    if current_user.role == UserRole.USER:
        filters.user_id = current_user.id
    elif current_user.role == UserRole.MANAGER:
        filters.cafe_id = current_user.cafe_id
    return await booking_crud.get_all(
        session=session,
        show_active=show_active,
        cafe_id=filters.cafe_id,
        user_id=filters.user_id,
    )


@router.get(
    '/{booking_id}',
    response_model=BookingInfo,
    status_code=OK,
    responses=error_responses(*RESOURCE_DETAIL),
    summary='Получение информации о бронировании по его ID.',
)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
    booking_service: BookingServiceDep,
) -> Booking:
    """Получение информации о бронировании по его ID.

    Для администраторов - любое бронирование.
    Для менеджера - бронирование своего кафе.
    Для пользователей - только свое бронирование.
    """
    booking = await booking_service.get_booking_or_raise(booking_id=booking_id)
    await booking_service.check_user_permission(booking=booking, user=current_user)
    return booking


@router.post(
    '',
    response_model=BookingInfo,
    status_code=CREATED,
    responses=error_responses(*BOOKING_CREATE),
    summary='Создает новое бронирования.',
)
async def create_booking(
    current_user: CurrentUser,
    new_booking: BookingCreate,
    booking_service: BookingServiceDep,
) -> Booking:
    """Создание нового бронирования возможно только авторизованными пользователями."""
    booking, manager_notification_id = await booking_service.create_booking_with_notifications(
        current_user,
        new_booking,
    )
    send_booking_notification.delay(str(manager_notification_id))
    return booking


@router.patch(
    '/{booking_id}',
    response_model=BookingInfo,
    status_code=OK,
    responses=error_responses(*RESOURCE_UPDATE),
    summary='Обновление информации о бронировании по его ID.',
)
async def update_booking(
    current_user: CurrentUser,
    booking_id: uuid.UUID,
    session: DBSession,
    update_data: BookingUpdate,
    booking_service: BookingServiceDep,
) -> Booking:
    """Обновление информации о бронировании по его ID.

    Независимо от роли не доступно обновление бронирования со статусом ACTIVE или COMPLETED.
    Для администраторов дступно обновлние всех бронирования.
    Для менеджера - обновление бронирований своего кафею
    Для пользователей - только свои активные бронирования за исключением полей
    status и is_active.
    """
    booking, manager_notification_id = await booking_service.update_booking_with_notifications(
        current_user=current_user,
        booking_id=booking_id,
        update_data=update_data,
    )
    send_booking_notification.delay(str(manager_notification_id))
    return booking
