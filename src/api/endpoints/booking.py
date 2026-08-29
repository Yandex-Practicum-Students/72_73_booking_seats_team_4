import uuid

from fastapi import APIRouter, status
from loguru import logger

from api.dependencies.cafe import get_cafe_or_404
from api.dependencies.permissions import CurrentUser
from api.errors import APIError
from api.responses import error_responses
from crud.booking import booking_crud
from models.booking import Booking
from models.user import UserRole
from schemas.booking import BookingCreate, BookingInfo, BookingUpdate
from services.booking import (
    FilterParam,
    check_booking_status,
    check_cafe_has_tables_slots,
    check_double_booking_exsist,
    check_number_geusts_not_more_seat_number,
    check_only_is_active_changes,
    check_role_user_cant_not_changed_is_active,
    check_user_have_same_slot,
    check_user_permission,
    get_booking_or_raise,
    split_tables_slots,
)

from core.db import DBSession

router = APIRouter()


@router.get(
    '',
    response_model=list[BookingInfo],
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Получение списка бронирований',
)
async def get_all_bookings(
    current_user: CurrentUser,
    session: DBSession,
    filters: FilterParam,
) -> list[Booking]:
    """Получение списка бронирований.

    Для администраторов - все бронирования (с возможностью выбора).
    Для менеджера - все активные бронирования своего кафе (с возможностью выбора).
    Для пользователей - только свои активные бронирования(параметры игнорируются, кроме ID кафе).
    """
    logger.info('Фильтрует параметры в зависимости от роли пользователя для получения списка бронирований.')
    if current_user.role == UserRole.USER:
        filters.show_active = True
        filters.user_id = current_user.id
    elif current_user.role == UserRole.MANAGER:
        if filters.show_active is None:
            filters.show_active = True
        filters.cafe_id = current_user.cafe_id
    return await booking_crud.get_all(
        session=session,
        show_active=filters.show_active,
        cafe_id=filters.cafe_id,
        user_id=filters.user_id,
    )


@router.get(
    '/{booking_id}',
    response_model=BookingInfo,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Получение информации о бронировании по его ID.',
)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> Booking:
    """Получение информации о бронировании по его ID.

    Для администраторов - любое бронирование.
    Для менеджера - бронирование своего кафе.
    Для пользователей - только свое бронирование.
    """
    booking = await get_booking_or_raise(booking_id=booking_id, session=session)
    await check_user_permission(booking=booking, user=current_user)
    return booking


@router.post(
    '',
    response_model=BookingInfo,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Создает новое бронирования.',
)
async def create_booking(
    current_user: CurrentUser,
    session: DBSession,
    new_booking: BookingCreate,
) -> Booking:
    """Создание нового бронирования возможно только авторизованными пользователями."""
    table_slot_ids, table_ids, slot_ids = split_tables_slots(new_booking.tables_slots)
    await get_cafe_or_404(
        cafe_id=new_booking.cafe_id,
        session=session,
    )
    await check_cafe_has_tables_slots(
        session=session,
        cafe_id=new_booking.cafe_id,
        table_ids=table_ids,
        slot_ids=slot_ids,
    )
    await check_double_booking_exsist(
        session=session,
        cafe_id=new_booking.cafe_id,
        booking_date=new_booking.booking_date,
        table_slot_ids=table_slot_ids,
    )
    await check_user_have_same_slot(
        session=session,
        booking_date=new_booking.booking_date,
        user_id=current_user.id,
        slot_ids=slot_ids,
    )
    await check_number_geusts_not_more_seat_number(
        session=session,
        guest_number=new_booking.guest_number,
        table_ids=table_ids,
    )
    return await booking_crud.create(
        obj_in=new_booking,
        session=session,
        current_user=current_user,
    )


@router.patch(
    '/{booking_id}',
    response_model=BookingInfo,
    status_code=status.HTTP_200_OK,
    responses=error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
    summary='Обновление информации о бронировании по его ID.',
)
async def update_booking(
    current_user: CurrentUser,
    booking_id: uuid.UUID,
    session: DBSession,
    update_data: BookingUpdate,
) -> Booking:
    """Обновление информации о бронировании по его ID.

    Независимо от роли не доступно обновление бронирования со статусом ACTIVE или COMPLETED.
    Для администраторов дступно обновлние всех бронирования.
    Для менеджера - обновление бронирований своего кафею
    Для пользователей - только свои активные бронирования за исключением полей
    status и is_active.
    """
    db_booking = await get_booking_or_raise(
        booking_id=booking_id,
        session=session,
    )

    await check_user_permission(booking=db_booking, user=current_user)

    logger.info('Проверяет статус бронирования id{}', db_booking.id)
    check_booking_status(db_booking)

    logger.info('Проверяет активно ли бронирование для пользователя с ролью User.')
    if not db_booking.is_active and current_user.role == UserRole.USER:
        logger.warning(
            'Бронирование id {} с полем is_active=false для пользователя не доступно',
            db_booking.id,
        )
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Бронирование удалено.',
        )

    logger.info('Проверка, что изменение поля is_active на false проходит без изменения други полей')
    check_only_is_active_changes(update_data)

    logger.info('Проверка изменения поля tables_slots')
    if update_data.tables_slots is not None:
        table_slot_ids, table_ids, slot_ids = split_tables_slots(update_data.tables_slots)
        await check_cafe_has_tables_slots(
            session=session,
            cafe_id=db_booking.cafe_id,
            table_ids=table_ids,
            slot_ids=slot_ids,
        )

        if update_data.booking_date:
            booking_date = update_data.booking_date
        else:
            booking_date = db_booking.booking_date

        await check_double_booking_exsist(
            session=session,
            cafe_id=db_booking.cafe_id,
            booking_date=booking_date,
            table_slot_ids=table_slot_ids,
            booking_id=db_booking.id,
        )

        await check_user_have_same_slot(
            session=session,
            booking_date=booking_date,
            user_id=db_booking.user_id,
            slot_ids=slot_ids,
            booking_id=db_booking.id,
        )

    logger.info(
        'Проверяет обновлялись ли поля tables_slots и/или guest_number '
        'для сравенения колиичества гостей и мест.',
    )
    if update_data.tables_slots is not None or update_data.guest_number is not None:
        if update_data.guest_number is not None:
            guest_number = update_data.guest_number
        else:
            guest_number = db_booking.guest_number
        if update_data.tables_slots is None:
            table_slot_ids, table_ids, slot_ids = split_tables_slots(db_booking.tables_slots)
        await check_number_geusts_not_more_seat_number(
            session=session,
            guest_number=guest_number,
            table_ids=table_ids,
        )

    logger.info('Поверка на возможность редактирования поля is_active бронирования пользователем.')
    check_role_user_cant_not_changed_is_active(update_data, current_user)

    return await booking_crud.update(
        session=session,
        db_booking=db_booking,
        obj_in=update_data,
    )
