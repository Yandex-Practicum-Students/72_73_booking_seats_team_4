from datetime import datetime, time, timedelta, timezone

from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from crud.booking import BookingCRUD, booking_crud
from crud.notification import NotificationCRUD, notification_crud
from models.booking import Booking, StatusBooking
from models.notification import NotificationType
from schemas.booking import BookingCreate, BookingUpdate

REMINDER_MINUTES_BEFORE = 180
DEFAULT_BOOKING_TIME = time(12, 0, tzinfo=timezone.utc)


class BookingService:
    """Сервис создания бронирования с уведомлениями.

    Оборачивает BookingCRUD (create, update) функционалом создания уведомлений.

    - Уведомления менеджеру направляются сразу после создания, изменения, отмены брони
    - Напоминания гостю направляются за REMINDER_MINUTES_BEFORE до start_time самого раннего слота в брони

    ВАЖНО: в BookingCRUD-методах create и update коммитить не нужно для атомарности транзакций.

    Пример использования в ендпоинте:
    ```
    @router.post('/', response_model=BookingSchema)
        async def create_booking(
            obj_in: BookingCreate,
            session: AsyncSession = Depends(get_session),
        ):
    service = BookingService(session, redis)
    return await service.create_booking(obj_in)
    ```
    """

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        booking_crud: BookingCRUD = booking_crud,
        notification_crud: NotificationCRUD = notification_crud,
    ) -> None:
        """Настройки экземпляра сервиса."""
        self.session = session
        self.redis = redis
        self.booking_crud = booking_crud
        self.notification_crud = notification_crud

    def _get_reminder_time(
        self,
        booking: Booking,
        minutes_before: int = REMINDER_MINUTES_BEFORE,
    ) -> datetime:
        """Расчёт времени напоминания за N минут до начала визита."""
        earliest_time = DEFAULT_BOOKING_TIME

        table_slots = getattr(booking, 'table_slot', None) or []
        start_times = [
            table_slot.slot.start_time
            for table_slot in table_slots
            if getattr(table_slot, 'slot', None) and table_slot.slot.start_time is not None
        ]
        if start_times:
            earliest_time = min(start_times)

        booking_dt = datetime.combine(booking.booking_date, earliest_time, tzinfo=timezone.utc)
        reminder_time = booking_dt - timedelta(minutes=minutes_before)

        return max(reminder_time, datetime.now(timezone.utc))

    async def create_booking(self, obj_in: BookingCreate) -> Booking:
        """Создание бронирования с уведомлением."""
        booking = await self.booking_crud.create(obj_in, self.session, self.redis)

        await self.notification_crud.create_for_booking(
            booking_id=booking.id,
            type_=NotificationType.CREATED,
            scheduled_at=datetime.now(timezone.utc),
            session=self.session,
        )

        await self.notification_crud.create_for_booking(
            booking_id=booking.id,
            type_=NotificationType.REMINDER_CLIENT,
            scheduled_at=self._get_reminder_time(booking),
            session=self.session,
        )

        await self.session.commit()
        await self.session.refresh(booking)

        logger.info('Бронирование {id} создано', id=booking.id)
        return booking

    async def update_booking(self, booking: Booking, obj_in: BookingUpdate) -> Booking:
        """Редактирование бронирования с уведомлением."""
        old_status = booking.status

        booking = await self.booking_crud.update(
            db_obj=booking,
            obj_in=obj_in,
            session=self.session,
            redis=self.redis,
        )

        now = datetime.now(timezone.utc)

        if booking.status == StatusBooking.CANCELED:
            if old_status != StatusBooking.CANCELED:
                await self.notification_crud.cancel_pending_for_booking(
                    booking_id=booking.id,
                    session=self.session,
                )
                await self.notification_crud.create_for_booking(
                    booking_id=booking.id,
                    type_=NotificationType.CANCELED,
                    scheduled_at=now,
                    session=self.session,
                )
        else:
            await self.notification_crud.cancel_pending_for_booking(
                booking_id=booking.id,
                session=self.session,
            )
            await self.notification_crud.create_for_booking(
                booking_id=booking.id,
                type_=NotificationType.UPDATED,
                scheduled_at=now,
                session=self.session,
            )
            await self.notification_crud.create_for_booking(
                booking_id=booking.id,
                type_=NotificationType.REMINDER_CLIENT,
                scheduled_at=self._get_reminder_time(booking),
                session=self.session,
            )

        await self.session.commit()
        await self.session.refresh(booking)

        logger.info('Бронирование {id} изменено', id=booking.id)
        return booking
