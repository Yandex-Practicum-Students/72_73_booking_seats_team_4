from collections.abc import Mapping

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from crud.user import UserAlreadyExistsError, UserNotFoundError
from schemas.error import CustomError


def custom_error_response(
    status_code: int,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Возвращает ошибку в едином формате из спецификации."""
    error = CustomError(code=status_code, message=message)
    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(),
        headers=dict(headers) if headers is not None else None,
    )


def _validation_error_message(exception: RequestValidationError) -> str:
    """Собирает ошибки валидации в одно понятное сообщение."""
    messages = []
    for error in exception.errors():
        location = '.'.join(str(part) for part in error['loc'] if part != 'body')
        message = error['msg']
        messages.append(f'{location}: {message}' if location else message)
    return '; '.join(messages)


async def http_exception_handler(
    _: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    """Преобразует стандартные HTTPException в формат CustomError."""
    return custom_error_response(
        exception.status_code,
        str(exception.detail),
        exception.headers,
    )


async def request_validation_error_handler(
    _: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    """Преобразует ошибки FastAPI/Pydantic в формат CustomError."""
    return custom_error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        _validation_error_message(exception),
    )


async def user_already_exists_handler(
    _: Request,
    __: UserAlreadyExistsError,
) -> JSONResponse:
    """Возвращает единый ответ при конфликте уникальных полей."""
    return custom_error_response(
        status.HTTP_400_BAD_REQUEST,
        'Пользователь с такими данными уже существует.',
    )


async def user_not_found_handler(
    _: Request,
    __: UserNotFoundError,
) -> JSONResponse:
    """Возвращает единый ответ, если пользователь не найден."""
    return custom_error_response(
        status.HTTP_404_NOT_FOUND,
        'Пользователь не найден.',
    )
