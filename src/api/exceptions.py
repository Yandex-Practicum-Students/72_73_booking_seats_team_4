from fastapi import Request, status
from fastapi.responses import JSONResponse

from crud.user import UserAlreadyExistsError, UserNotFoundError


async def user_already_exists_handler(
    _: Request,
    __: UserAlreadyExistsError,
) -> JSONResponse:
    """Возвращает единый ответ при конфликте уникальных полей."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={'detail': 'Пользователь с такими данными уже существует.'},
    )


async def user_not_found_handler(
    _: Request,
    __: UserNotFoundError,
) -> JSONResponse:
    """Возвращает единый ответ, если пользователь не найден."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={'detail': 'Пользователь не найден.'},
    )
