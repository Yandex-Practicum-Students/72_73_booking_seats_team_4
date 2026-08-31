import uuid
from datetime import date
from typing import Annotated, List, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PositiveInt

from models.booking import StatusBooking
from schemas.base import BaseInfoScheme, IdScheme
from schemas.cafe import CafeShortInfo
from schemas.slots import TimeSlotShortInfo
from schemas.table import TableShortInfo
from schemas.user import UserShortInfo

from core.constants import BOOKING_NOTE_MAX_LENGTH


def check_booking_date_not_past(value: date) -> date:
    """Проверка того, что дата брорнирования не является прошедшей датой."""
    if value < date.today():
        error = 'Дата бронирования не может быть меньше текущей даты'
        raise ValueError(error)
    return value


BookinDateNotPast = Annotated[date, AfterValidator(check_booking_date_not_past)]


class BookingTableSlot(BaseModel):
    """Схема для промежуточно модели BookingTableSlot.

    Используется в качестве вложенной схемы
    для схем BookingCreate, BookingUpdate.
    """

    table_id: uuid.UUID
    slot_id: uuid.UUID


class BookingTableSlotShortInfo(BaseModel):
    """Вспомогательная схема.

    Используется в качестве вложеной схемы в схему BookingInfo.
    """

    table: TableShortInfo
    slot: TimeSlotShortInfo
    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    """Базовый класс схемы Booking.

    От нее наследуют схемы BookingCreate и BookingInfo.
    """

    guest_number: PositiveInt
    note: Optional[str] = Field(None, max_length=BOOKING_NOTE_MAX_LENGTH)
    booking_date: date
    model_config = ConfigDict(extra='forbid')


class BookingCreate(BookingBase):
    """Класс схемы, описывающий создание бронирования."""

    cafe_id: uuid.UUID
    tables_slots: List[BookingTableSlot]
    booking_date: BookinDateNotPast


class BookingUpdate(BookingBase):
    """Класс схемы, описывающей изменение бронирования."""

    tables_slots: Optional[List[BookingTableSlot]] = Field(None)
    guest_number: Optional[PositiveInt] = Field(None)
    booking_date: Optional[BookinDateNotPast] = Field(None)

    status: Optional[StatusBooking] = Field(None)
    is_active: Optional[bool] = Field(None)


class BookingInfo(IdScheme, BookingBase, BaseInfoScheme):
    """Класс схемы, описывающий полные данные о бронировании."""

    user: UserShortInfo
    cafe: CafeShortInfo
    tables_slots: List[BookingTableSlotShortInfo]
    status: StatusBooking
