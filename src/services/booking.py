import uuid
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from loguru import logger
from sqlalchemy import and_, or_, select, tuple_
from sqlalchemy.orm import selectinload

from api.errors import APIError
from crud.booking import booking_crud
from models.booking import Booking, BookingTablesSlots, StatusBooking
from models.slots import Slot
from models.table import Table
from models.user import User, UserRole
from schemas.booking import BookingUpdate

from core.db import DBSession


class BookingNotFoundError(APIError):
    """Бронирование не найдено."""

    def __init__(self) -> None:
        """Бронирование не найдено."""
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message='Бронирование не найдено.',
        )


class BookingAlreadyExistsError(APIError):
    """Бронирование уже существует."""

    def __init__(self) -> None:
        """Бронирование уже существует."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Бронирование уже существует.',
        )


class CrossSlotsExistsError(APIError):
    """Существует бронирование с пересекающимися слотами."""

    def __init__(self) -> None:
        """Существует бронирование с пересекающимися слотами."""
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='У пользователя есть бронирования с пересекающимися слотами.',
        )


@dataclass
class QueryParamFilter:
    """Фильтр query-параметров."""

    show_active: Optional[bool] = None
    cafe_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None


FilterParam = Annotated[QueryParamFilter, Depends(QueryParamFilter)]


def split_tables_slots(tables_slots: list[tuple[int, int]]) -> tuple[list, list, list]:
    """Обрабатывает поле tables_slots из запроса.

    Разбивает на следующие списки для дальнейшего использования:
    пары стол_id-слот_id, столы_id, слоты_id.
    """
    table_slot_ids = [(item.table_id, item.slot_id) for item in tables_slots]
    table_ids = [table_id for table_id, slot_id in table_slot_ids]
    slot_ids = [slot_id for table_id, slot_id in table_slot_ids]
    return table_slot_ids, table_ids, slot_ids


async def get_booking_or_raise(
    booking_id: uuid.UUID,
    session: DBSession,
) -> Booking:
    """Возвращает бронирование или сообщает, что объект не найден."""
    logger.info('Получение бронирования по id: {}.', booking_id)
    booking = await booking_crud.get(
        obj_id=booking_id,
        session=session,
        options=[
            selectinload(Booking.user),
            selectinload(Booking.cafe),
            selectinload(Booking.tables_slots.and_(BookingTablesSlots.is_active)),
        ],
    )
    if booking is None:
        logger.warning('Бронирование с id: {} не найдено.', booking_id)
        raise BookingNotFoundError
    logger.info('Получение бронирование по id: {}.', booking_id)
    return booking


async def check_user_permission(
    booking: Booking,
    user: User,
) -> None:
    """Проверяет наличие права доступа к бронированию у пользователя и менеджера."""
    logger.info('Проверяет права пользователя на доступ к бронированию.')
    if user.role == UserRole.USER and user.id != booking.user_id:
        logger.warning('У пользователя с ролью User нет доступа к бронированию id {}', booking.id)
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='Доступ запрещен.',
        )
    if user.role == UserRole.MANAGER and (user.id != booking.user_id and user.cafe_id != booking.cafe_id):
        logger.warning('У менеджера нет доступа к бронированию id {} в кафе {}', booking.id, booking.cafe_id)
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            message='Доступ запрещен.',
        )


async def check_double_booking_exsist(
    session: DBSession,
    cafe_id: uuid.UUID,
    booking_date: date,
    table_slot_ids: list,
    booking_id: Optional[uuid.UUID] = None,
) -> None:
    """Проверяет на наличе повторного бронирования."""
    logger.info('Проверка на наличие повторного бронирования.')
    booking = (
        select(Booking)
        .join(Booking.tables_slots)
        .where(
            Booking.cafe_id == cafe_id,
            Booking.booking_date == booking_date,
            Booking.status != StatusBooking.CANCELED,
            Booking.is_active,
            tuple_(BookingTablesSlots.table_id, BookingTablesSlots.slot_id).in_(table_slot_ids),
        )
    )
    if booking_id is not None:
        booking = booking.where(Booking.id != booking_id)
    booking = await session.execute(booking)
    result = booking.scalars().first()
    if result is not None:
        logger.warning(
            'Повторное бронирование. Уже существует бронирование id {} с такими параметрами.',
            result.id,
        )
        raise BookingAlreadyExistsError


async def check_user_have_same_slot(
    session: DBSession,
    booking_date: date,
    user_id: uuid.UUID,
    slot_ids: list,
    booking_id: Optional[uuid.UUID] = None,
) -> None:
    """Проверяет наличие у пользователя бронирований с пересекающимися слотами."""
    logger.info('Проверка на пересекающиеся слоты пользователя.')
    slots = await session.execute(select(Slot).where(Slot.id.in_(slot_ids)))
    start_end_time_slots_new_booking = [(slot.start_time, slot.end_time) for slot in slots.scalars().all()]
    cross_slots = [
        and_(Slot.start_time < new_end, new_start < Slot.end_time)
        for new_start, new_end in start_end_time_slots_new_booking
    ]
    bookings_user_cros_slots = (
        select(Booking)
        .join(Booking.tables_slots)
        .join(BookingTablesSlots.slot)
        .where(
            Booking.user_id == user_id,
            Booking.booking_date == booking_date,
            Booking.status != StatusBooking.CANCELED,
            Booking.is_active,
            or_(*cross_slots),
        )
    )
    if booking_id is not None:
        bookings_user_cros_slots = bookings_user_cros_slots.where(Booking.id != booking_id)
    bookings_user_cros_slots = await session.execute(bookings_user_cros_slots)
    if bookings_user_cros_slots.scalars().first() is not None:
        logger.warning('Пользователь имеет пересекающие слоты в других бронированиях.')
        raise CrossSlotsExistsError


async def check_cafe_has_tables_slots(
    session: DBSession,
    cafe_id: uuid.UUID,
    table_ids: list,
    slot_ids: list,
) -> None:
    """Проверяет существует ли в кафе указанные столы и слоты."""
    logger.info('Проверяет существует ли в кафе указанные столы и слоты.')
    found_table_ids = await session.execute(
        select(Table.id).where(
            Table.cafe_id == cafe_id,
            Table.id.in_(table_ids),
            Table.is_active,
        ),
    )
    found_table_ids = set(found_table_ids.scalars().all())
    unknown_table_ids = set(table_ids) - found_table_ids
    if unknown_table_ids:
        logger.warning('В кафе не найдены столы(по id){}', unknown_table_ids)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'В кафе не найдены столы(по id) {unknown_table_ids}',
        )

    found_slot_ids = await session.execute(
        select(Slot.id).where(
            Slot.cafe_id == cafe_id,
            Slot.id.in_(slot_ids),
            Slot.is_active,
        ),
    )
    found_slot_ids = set(found_slot_ids.scalars().all())
    unknown_slot_ids = set(slot_ids) - found_slot_ids
    if unknown_slot_ids:
        logger.warning('В кафе не найдены слоты(по id){}', unknown_slot_ids)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'В кафе не найдены слот с id {unknown_slot_ids}',
        )


async def check_number_geusts_not_more_seat_number(
    session: DBSession,
    guest_number: int,
    table_ids: list,
) -> None:
    """Проверка вместимости гостей.

    Проверяет, что количество гостей в бронировании не превышает общего количества
    сидячих мест за забронированными столиками.
    """
    logger.info('Сравнивает количество гостей и количество сидячих мест.')
    seat_number_tables = await session.execute(
        select(Table.seat_number).where(Table.id.in_(table_ids)),
    )
    seat_number_tables = sum(seat_number_tables.scalars().all())
    if guest_number > seat_number_tables:
        logger.warning(
            'Количество гостей {} превышает количество мест {} за столами.',
            guest_number,
            seat_number_tables,
        )
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=(
                f'Количество гостей {guest_number} превышае количество мест {seat_number_tables} за столами.'
            ),
        )


def check_only_is_active_changes(update_data: BookingUpdate) -> None:
    """Проверяет изменение поля is_active.

    Проверка что изменение значения поля is_active на false проходит без изменения други полей.
    """
    if update_data.is_active is not None and not update_data.is_active:
        extra_fields = update_data.model_fields_set - set({'is_active'})
        if extra_fields:
            logger.warning('Присовение полю is_active значения false должно быть без изменения других полей')
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message='Деактивация брони должна осуществляться без изменения других полей.',
            )


def check_booking_status(db_booking: Booking) -> None:
    """Проверка статуса бронирования и возможности изменения."""
    if db_booking.status == StatusBooking.ACTIVE or db_booking.status == StatusBooking.COMPLETED:
        logger.warning('Статус бронирования {} не допускает внесения изменений', db_booking.status)
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Статус бронирования не допускает внесение изменений.',
        )


def check_role_user_cant_not_changed_is_active(update_data: BookingUpdate, current_user: User) -> None:
    """Проверка что обычный пользователь не меняет поле is_active."""
    if update_data.is_active is not None and current_user.role == UserRole.USER:
        logger.warning(
            'Пользователь с ролью USER не может редактировать поле is_active бронирования.',
        )
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message='Пользовтель не может реадктировать поле is_active.',
        )
