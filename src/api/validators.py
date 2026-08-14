from datetime import time
from typing import Optional

from pydantic import model_validator


class TimeValidatorMixin:
    """Миксин для валидации временных интервалов."""

    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode="after")
    def validate_times(self) -> "TimeValidatorMixin":
        """Проверка: время начала меньше времени окончания."""
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError(
                    "Время начала должно быть меньше времени окончания",
                )
        return self
