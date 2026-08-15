from datetime import time
from typing import Any, Optional

import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
from pydantic import model_validator


def normalize_username(value: Any) -> Any:
    """Удаляет внешние пробелы из имени пользователя."""
    if isinstance(value, str):
        return value.strip()
    return value


def normalize_phone(value: Any) -> Any:
    """Проверяет международный номер и приводит его к формату E.164."""
    if value is None or not isinstance(value, str):
        return value

    try:
        phone = phonenumbers.parse(value.strip(), None)
    except NumberParseException as error:
        raise ValueError(
            'Укажите телефон в международном формате, например +79991234567',
        ) from error

    if not phonenumbers.is_valid_number(phone):
        raise ValueError('Указан некорректный номер телефона')

    return phonenumbers.format_number(
        phone,
        phonenumbers.PhoneNumberFormat.E164,
    )


def normalize_login(value: Any) -> Any:
    """Нормализует email или телефон перед аутентификацией."""
    if not isinstance(value, str):
        return value

    value = value.strip()
    if '@' in value:
        return value.lower()
    return normalize_phone(value)


def normalize_time(value: Any) -> Any:
    """Нормализация времени из строки в time.

    Поддерживает форматы:
    - HH:MM:SS (полный формат)
    - HH:MM (добавляет :00 автоматически)
    - time (убирает микросекунды)
    """
    if isinstance(value, time):
        return value.replace(microsecond=0) if value.microsecond else value

    if isinstance(value, str):
        if len(value.split(':')) == 2:
            value = f'{value}:00'
        try:
            return time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError('Некорректный формат времени. Используйте HH:MM или HH:MM:SS') from exc
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
