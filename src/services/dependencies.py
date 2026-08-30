from typing import Annotated

from fastapi import Depends

from services.booking import BookingService
from services.notification import NotificationService

from core.db import DBSession


def get_notification_service(session: DBSession) -> NotificationService:
    """Провайдер сервиса уведомлений."""
    return NotificationService(session=session)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


def get_booking_service(
    session: DBSession,
    notification_service: NotificationServiceDep,
) -> BookingService:
    """Провайдер сервиса бронирования с внедренным NotificationService."""
    return BookingService(
        session=session,
        notification_service=notification_service,
    )


BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]
