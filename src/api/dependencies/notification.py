from typing import Annotated

from fastapi import Depends

from services.notification import NotificationService

from core.db import DBSession


def get_notification_service(session: DBSession) -> NotificationService:
    """Провайдер сервиса уведомлений."""
    return NotificationService(session=session)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
