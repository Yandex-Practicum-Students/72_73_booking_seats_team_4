import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import and_, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from api.dependencies.cafe import get_cafe_or_404
from api.dependencies.permissions import CurrentUser
from crud.booking import BookingCRUD, booking_crud
from exceptions.base import APIError
from exceptions.booking import (
    BookingAlreadyExistsError,
    BookingNotFoundError,
    CrossSlotsExistsError,
    TableAlreadyBookedError,
)
from models.booking import Booking, BookingTablesSlots, StatusBooking
from models.slots import Slot
from models.table import Table
from models.user import User, UserRole
from schemas.booking import BookingCreate, BookingUpdate
from services.notification import NotificationService

from core.db import DBSession


class BookingService:
    """Сервис создания бронирования."""

    def __init__(
        self,
        session: DBSession,
        notification_service: NotificationService,
        booking_crud: BookingCRUD = booking_crud,
    ) -> None:
        """Настройки экземпляра сервиса бронирования."""
        self.session = session
        self.crud = booking_crud
        self.notification_service = notification_service

    def split_tables_slots(self, tables_slots: list[tuple[int, int]]) -> tuple[list, list, list]:
        """Обрабатывает поле tables_slots из запроса.

        Разбивает на следующие списки для дальнейшего использования:
        пары стол_id-слот_id, столы_id, слоты_id.
        """
        table_slot_ids = [(item.table_id, item.slot_id) for item in tables_slots]
        table_ids = [table_id for table_id, slot_id in table_slot_ids]
        slot_ids = [slot_id for table_id, slot_id in table_slot_ids]
        return table_slot_ids, table_ids, slot_ids

    async def get_booking_or_raise(
        self,
        booking_id: uuid.UUID,
    ) -> Booking:
        """Возвращает бронирование или сообщает, что объект не найден."""
        logger.info('Получение бронирования по id: {}.', booking_id)
        booking = await self.crud.get(
            obj_id=booking_id,
            session=self.session,
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

    async def check_user_permission(self, booking: Booking, user: User) -> None:
        """Проверяет наличие права доступа к бронированию у пользователя и менеджера."""
        logger.info('Проверяет права пользователя на доступ к бронированию.')
        if user.role == UserRole.USER and user.id != booking.user_id:
            logger.warning('У пользователя с ролью User нет доступа к бронированию id {}', booking.id)
            raise APIError(
                status_code=status.HTTP_403_FORBIDDEN,
                message='Доступ запрещен.',
            )
        if user.role == UserRole.MANAGER and (user.id != booking.user_id and user.cafe_id != booking.cafe_id):
            logger.warning(
                'У менеджера нет доступа к бронированию id {} в кафе {}',
                booking.id,
                booking.cafe_id,
            )
            raise APIError(
                status_code=status.HTTP_403_FORBIDDEN,
                message='Доступ запрещен.',
            )

    async def check_double_booking_exsist(
        self,
        cafe_id: uuid.UUID,
        booking_date: date,
        table_slot_ids: list,
        booking_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Проверяет на наличие повторного бронирования."""
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
        booking = await self.session.execute(booking)
        result = booking.scalars().first()
        if result is not None:
            logger.warning(
                'Повторное бронирование. Уже существует бронирование id {} с такими параметрами.',
                result.id,
            )
            raise BookingAlreadyExistsError

    async def check_user_have_same_slot(
        self,
        booking_date: date,
        user_id: uuid.UUID,
        slot_ids: list,
        booking_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Проверяет наличие у пользователя бронирований с пересекающимися слотами."""
        logger.info('Проверка на пересекающиеся слоты пользователя.')
        slots = await self.session.execute(select(Slot).where(Slot.id.in_(slot_ids)))
        start_end_time_slots_new_booking = [
            (slot.start_time, slot.end_time) for slot in slots.scalars().all()
        ]
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
        bookings_user_cros_slots = await self.session.execute(bookings_user_cros_slots)
        if bookings_user_cros_slots.scalars().first() is not None:
            logger.warning('Пользователь имеет пересекающие слоты в других бронированиях.')
            raise CrossSlotsExistsError

    async def check_booking_time_earlier_start_time_slot(
        self,
        booking_date: date,
        slot_ids: list,
    ) -> None:
        """Проверяет, что начало времени слота еще не наступило."""
        logger.info('Проверяет, что начало времени слота еще не наступило.')
        current_day = datetime.now(timezone.utc)
        if booking_date == current_day.date():
            current_time = current_day.timetz()
            slots = await self.session.execute(select(Slot).where(Slot.id.in_(slot_ids)))
            start_time_slots_new_booking = [slot.start_time for slot in slots.scalars().all()]
            exist_problem_start_time = any(
                [start_time < current_time for start_time in start_time_slots_new_booking],
            )
            if exist_problem_start_time:
                logger.warning(
                    'Нельзя бронировать слот, время которого уже началось.',
                )
                raise APIError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message=('Нельзя бронировать слот, время которого уже началось.'),
                )

    async def check_cafe_has_tables_slots(
        self,
        cafe_id: uuid.UUID,
        table_ids: list,
        slot_ids: list,
    ) -> None:
        """Проверяет существует ли в кафе указанные столы и слоты."""
        logger.info('Проверяет существует ли в кафе указанные столы и слоты.')
        found_table_ids = await self.session.execute(
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

        found_slot_ids = await self.session.execute(
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
        self,
        guest_number: int,
        table_ids: list,
    ) -> None:
        """Проверка вместимости гостей.

        Проверяет, что количество гостей в бронировании не превышает общего количества
        сидячих мест за забронированными столиками.
        """
        logger.info('Сравнивает количество гостей и количество сидячих мест.')
        seat_number_tables = await self.session.execute(
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
                    f'Количество гостей {guest_number} превышает '
                    f'количество мест {seat_number_tables} за столами.'
                ),
            )

    def check_only_is_active_changes(self, update_data: BookingUpdate) -> None:
        """Проверяет изменение поля is_active.

        Проверка что изменение значения поля is_active на false проходит без изменения други полей.
        """
        if update_data.is_active is not None and not update_data.is_active:
            extra_fields = update_data.model_fields_set - set({'is_active'})
            if extra_fields:
                logger.warning(
                    'Присовение полю is_active значения false должно быть без изменения других полей',
                )
                raise APIError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message='Деактивация брони должна осуществляться без изменения других полей.',
                )

    def check_booking_status(self, db_booking: Booking) -> None:
        """Проверка статуса бронирования и возможности изменения."""
        if db_booking.status == StatusBooking.ACTIVE or db_booking.status == StatusBooking.COMPLETED:
            logger.warning('Статус бронирования {} не допускает внесения изменений', db_booking.status)
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message='Статус бронирования не допускает внесение изменений.',
            )

    def check_role_user_cant_not_changed_is_active(
        self,
        update_data: BookingUpdate,
        current_user: User,
    ) -> None:
        """Проверка что обычный пользователь не меняет поле is_active."""
        if update_data.is_active is not None and current_user.role == UserRole.USER:
            logger.warning(
                'Пользователь с ролью USER не может редактировать поле is_active бронирования.',
            )
            raise APIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message='Пользовтель не может реадктировать поле is_active.',
            )

    async def create_booking_with_notifications(
        self,
        current_user: CurrentUser,
        new_booking: BookingCreate,
    ) -> tuple[Booking, uuid.UUID]:
        """Создает бронирование с напоминанием гостю и уведомлением менеджеров."""
        table_slot_ids, table_ids, slot_ids = self.split_tables_slots(new_booking.tables_slots)
        await get_cafe_or_404(cafe_id=new_booking.cafe_id, session=self.session)
        await self.check_cafe_has_tables_slots(
            cafe_id=new_booking.cafe_id,
            table_ids=table_ids,
            slot_ids=slot_ids,
        )
        await self.check_booking_time_earlier_start_time_slot(
            slot_ids=slot_ids,
            booking_date=new_booking.booking_date,
        )
        await self.check_double_booking_exsist(
            cafe_id=new_booking.cafe_id,
            booking_date=new_booking.booking_date,
            table_slot_ids=table_slot_ids,
        )
        await self.check_user_have_same_slot(
            booking_date=new_booking.booking_date,
            user_id=current_user.id,
            slot_ids=slot_ids,
        )
        await self.check_number_geusts_not_more_seat_number(
            guest_number=new_booking.guest_number,
            table_ids=table_ids,
        )

        try:
            booking = await self.crud.create(
                obj_in=new_booking,
                session=self.session,
                current_user=current_user,
            )
        except IntegrityError as error:
            await self.session.rollback()
            if 'uniq_active_booking_table_slot' in str(error.orig):
                raise TableAlreadyBookedError from error
            raise error

        manager_notification, _ = await self.notification_service.create_booking_notifications(booking)

        await self.session.commit()
        await self.session.refresh(booking)

        return booking, manager_notification.id

    async def update_booking_with_notifications(
        self,
        current_user: CurrentUser,
        booking_id: uuid.UUID,
        update_data: BookingUpdate,
    ) -> tuple[Booking, uuid.UUID]:
        """Обновляет информацию о бронировании с напоминанием гостю и уведомлением менеджеров."""
        db_booking = await self.get_booking_or_raise(booking_id=booking_id)

        await self.check_user_permission(booking=db_booking, user=current_user)

        logger.info('Проверяет статус бронирования id{}', db_booking.id)
        self.check_booking_status(db_booking)

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
        self.check_only_is_active_changes(update_data)

        logger.info('Проверка изменения поля tables_slots')
        if update_data.tables_slots is not None:
            table_slot_ids, table_ids, slot_ids = self.split_tables_slots(update_data.tables_slots)
            await self.check_cafe_has_tables_slots(
                cafe_id=db_booking.cafe_id,
                table_ids=table_ids,
                slot_ids=slot_ids,
            )

            if update_data.booking_date:
                booking_date = update_data.booking_date
            else:
                booking_date = db_booking.booking_date

            await self.check_double_booking_exsist(
                cafe_id=db_booking.cafe_id,
                booking_date=booking_date,
                table_slot_ids=table_slot_ids,
                booking_id=db_booking.id,
            )

            await self.check_user_have_same_slot(
                booking_date=booking_date,
                user_id=db_booking.user_id,
                slot_ids=slot_ids,
                booking_id=db_booking.id,
            )

        logger.info(
            'Проверяет обновлялись ли поля tables_slots и/или booking_date '
            'для сравенения текущего времени и времени начала слотов.',
        )
        if update_data.tables_slots is not None or update_data.booking_date is not None:
            if update_data.booking_date is not None:
                booking_date = update_data.booking_date
            else:
                booking_date = db_booking.booking_date
            if update_data.tables_slots is None:
                table_slot_ids, table_ids, slot_ids = self.split_tables_slots(db_booking.tables_slots)
            await self.check_booking_time_earlier_start_time_slot(
                booking_date=booking_date,
                slot_ids=slot_ids,
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
                table_slot_ids, table_ids, slot_ids = self.split_tables_slots(db_booking.tables_slots)
            await self.check_number_geusts_not_more_seat_number(
                guest_number=guest_number,
                table_ids=table_ids,
            )

        logger.info('Поверка на возможность редактирования поля is_active бронирования пользователем.')
        self.check_role_user_cant_not_changed_is_active(update_data, current_user)

        booking = await self.crud.update(session=self.session, db_booking=db_booking, obj_in=update_data)

        manager_notification, _ = await self.notification_service.update_booking_notifications(booking)
        await self.session.commit()
        await self.session.refresh(booking)

        return booking, manager_notification.id
