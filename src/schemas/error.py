from pydantic import BaseModel


class CustomError(BaseModel):
    """Единый формат ошибки API из спецификации проекта."""

    code: int
    message: str
