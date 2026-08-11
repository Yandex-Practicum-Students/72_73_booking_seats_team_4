from fastapi_users import schemas


class UserCommonFieldsMixin:
    """Миксин с общими полями схем пользователя."""

    ...


class UserCreate(schemas.BaseUserCreate):
    """Схема создания пользователя."""

    ...


class UserInfo(schemas.BaseUser[int]):
    """Схема полных данных о пользователе."""

    ...


class UserRole:
    """Схема пользовательских ролей."""

    ...


class UserShortInfo:
    """Схема полных данных о пользователе."""

    ...


class UserUpdate(schemas.BaseUserUpdate):
    """Схема редактирования пользователя."""

    ...
