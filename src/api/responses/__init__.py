from collections.abc import Mapping

from schemas.error import CustomError

ERROR_DESCRIPTIONS = {
    400: 'Ошибка в параметрах запроса',
    401: 'Неавторизованный пользователь',
    403: 'Доступ запрещён',
    404: 'Данные не найдены',
    413: 'Размер данных превышает допустимый',
    422: 'Ошибка валидации данных',
}


def error_responses(
    *status_codes: int,
    descriptions: Mapping[int, str] | None = None,
) -> dict[int, dict[str, object]]:
    """Формирует дополнительные ответы маршрута в формате CustomError."""
    custom_descriptions = descriptions or {}
    return {
        status_code: {
            'model': CustomError,
            'description': custom_descriptions.get(
                status_code,
                ERROR_DESCRIPTIONS[status_code],
            ),
        }
        for status_code in status_codes
    }
