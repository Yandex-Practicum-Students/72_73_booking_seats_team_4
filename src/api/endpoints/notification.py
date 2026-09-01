import uuid

from fastapi import APIRouter, Query

from api.dependencies.permissions import CurrentUser, StaffUser
from api.responses import error_responses
from api.responses.statuses import ACCEPTED, NOTIFICATION_DETAIL, NOTIFICATION_RETRY
from models import BookingNotification, NotificationStatus, NotificationType
from schemas.notification import BookingNotificationInfo
from services.dependencies import BookingServiceDep, NotificationServiceDep
from tasks.notifications import send_booking_notification

router = APIRouter()


@router.get(
    '/{booking_id}/notifications',
    response_model=list[BookingNotificationInfo],
    responses=error_responses(*NOTIFICATION_DETAIL),
    summary='Получение статусов уведомлений бронирования',
)
async def get_booking_notifications(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
    booking_service: BookingServiceDep,
    notification_service: NotificationServiceDep,
    notification_type: NotificationType | None = Query(None, alias='type'),
    notification_status: NotificationStatus | None = Query(None, alias='status'),
) -> list[BookingNotification]:
    """Возвращает доступную пользователю историю уведомлений бронирования."""
    booking = await booking_service.get_booking_or_raise(booking_id=booking_id)
    await booking_service.check_user_permission(
        booking=booking,
        user=current_user,
    )
    return await notification_service.get_booking_notifications(
        booking_id=booking_id,
        type_=notification_type,
        status_=notification_status,
    )


@router.get(
    '/{booking_id}/notifications/{notification_id}',
    response_model=BookingNotificationInfo,
    responses=error_responses(*NOTIFICATION_DETAIL),
    summary='Получение статуса уведомления',
)
async def get_booking_notification(
    booking_id: uuid.UUID,
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    booking_service: BookingServiceDep,
    notification_service: NotificationServiceDep,
) -> BookingNotification:
    """Возвращает одно уведомление после проверки доступа к бронированию."""
    booking = await booking_service.get_booking_or_raise(booking_id=booking_id)
    await booking_service.check_user_permission(
        booking=booking,
        user=current_user,
    )
    return await notification_service.get_notification_or_raise(
        booking_id=booking_id,
        notification_id=notification_id,
    )


@router.post(
    '/{booking_id}/notifications/{notification_id}/retry',
    response_model=BookingNotificationInfo,
    status_code=ACCEPTED,
    responses=error_responses(*NOTIFICATION_RETRY),
    summary='Повторная отправка неудачного уведомления',
)
async def retry_booking_notification(
    booking_id: uuid.UUID,
    notification_id: uuid.UUID,
    current_user: StaffUser,
    booking_service: BookingServiceDep,
    notification_service: NotificationServiceDep,
) -> BookingNotification:
    """Возвращает FAILED-уведомление в очередь по запросу сотрудника."""
    booking = await booking_service.get_booking_or_raise(booking_id=booking_id)
    await booking_service.check_user_permission(
        booking=booking,
        user=current_user,
    )
    notification = await notification_service.retry_failed_notification(
        booking_id=booking_id,
        notification_id=notification_id,
    )
    send_booking_notification.delay(str(notification.id))
    return notification
