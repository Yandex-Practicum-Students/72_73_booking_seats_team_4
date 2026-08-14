from datetime import date, time
from typing import Any, Optional

from pydantic import model_validator


def normalize_time(value: Any) -> Any:
    """Нормализация времени из строки в time."""
    if isinstance(value, time):
        return value.replace(microsecond=0) if value.microsecond else value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError('Некорректный формат времени. Используйте HH:MM:SS') from exc
    return value


class TimeValidatorMixin:
    """Миксин для кросс-полевой валидации временных интервалов."""

    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode='after')
    def validate_times(self) -> 'TimeValidatorMixin':
        """Проверка: время начала меньше времени окончания."""
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError(
                    'Время начала должно быть меньше времени окончания',
                )
        return self

    @model_validator(mode='after')
    def validate_booking_date(self) -> 'TimeValidatorMixin':
        """Проверка: дата бронирования не в прошлом."""
        if self.booking_date is not None:
            today = date.today()
            if self.booking_date < today:
                raise ValueError('Дата бронирования не может быть в прошлом')
        return self
