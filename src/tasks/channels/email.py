from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import UUID

import aiosmtplib
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from crud.user import user_crud
from tasks.channels.base import NotificationChannel


class EmailChannel(NotificationChannel):
    """Канал отправки уведомлений через email."""

    def __init__(
        self,
        session: AsyncSession,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        timeout: float = 10.0,
    ) -> None:
        """Настройка экземпляра класса."""
        self.session = session
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.timeout = timeout

    async def send(self, recipient_id: UUID, subject: str, body: str) -> None:
        """Отправка email уведомления."""
        user = await user_crud.get_or_raise(recipient_id, self.session)

        if not user.email:
            raise ValueError(f'У пользователя нет email: user_id={recipient_id}')

        await self._send_email(to_email=user.email, subject=subject, body=body)

        logger.info(
            'Email отправлен: to={user}, subject={subject}',
            user=user.email,
            subject=subject,
        )

    async def _send_email(self, to_email: str, subject: str, body: str) -> None:
        """Низкоуровневая отправка email через SMTP - aiosmtplib."""
        message = MIMEMultipart()
        message['From'] = self.from_email
        message['To'] = to_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain', 'utf-8'))

        await aiosmtplib.send(
            message,
            hostname=self.smtp_host,
            port=self.smtp_port,
            username=self.smtp_user,
            password=self.smtp_password,
            timeout=self.timeout,
        )
