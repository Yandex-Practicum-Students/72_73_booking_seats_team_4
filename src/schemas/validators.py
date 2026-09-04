import uuid
from datetime import time
from typing import Any, List, Optional

import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
from pydantic import ValidationInfo


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
    if any(char.isdecimal() for char in value):
        return normalize_phone(value)
    raise ValueError('В login необходимо указать email или телефон.')


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


def validate_time_range(
    start_time: Optional[time],
    end_time: Optional[time],
) -> None:
    """Проверка: start_time < end_time."""
    if start_time is not None and end_time is not None and start_time >= end_time:
        raise ValueError(
            'Время начала должно быть меньше времени окончания',
        )


def validate_empty_field(
    value: str | List[uuid.UUID],
    info: ValidationInfo,
) -> str | List[uuid.UUID]:
    """Проверяет, чобы поле не содержало пустую строку."""
    if (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and not value):
        raise ValueError(f'Обязательное поле {info.field_name} не должно быть пустым.')
    return value


def field_cannot_be_null(
    value: str | List[uuid.UUID],
    info: ValidationInfo,
) -> str | List[uuid.UUID]:
    """Проверяет, чтобы поле не имело значения null."""
    if value is None:
        error = f'Поле {info.field_name} не может содержать значение null!'
        raise ValueError(error)
    return value
