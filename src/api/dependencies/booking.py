from typing import Annotated

from fastapi import Depends

from api.dependencies.filters import QueryParamFilter
from api.dependencies.notification import NotificationServiceDep
from services.booking import BookingService

from core.db import DBSession


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

FilterParam = Annotated[QueryParamFilter, Depends(QueryParamFilter)]
