from typing import Any

import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException


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
