import uuid
from datetime import date
from typing import Annotated, List, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PositiveInt

from src.models.booking import StatusBooking
from src.schemas.base import FullBaseSchemeDB, IsActiveScheme
from src.schemas.cafe import CafeShortInfo
from src.schemas.slots import TimeSlotShortInfo
from src.schemas.table import TableShort
from src.schemas.user import UserShortInfo


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

    table: TableShort
    slot: TimeSlotShortInfo
    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    """Базовый класс схемы Booking.

    От нее наследуют схемы BookingCreate и BookingInfo.
    """

    guest_number: PositiveInt
    note: Optional[str] = Field(
        None,
    )
    booking_date: date


class BookingCreate(BookingBase):
    """Класс схемы, описывающий создание бронирования."""

    cafe_id: uuid.UUID
    tables_slots: List[BookingTableSlot]
    booking_date: BookinDateNotPast
    model_config = ConfigDict(extra='forbid')


class BookingUpdate(IsActiveScheme):
    """Класс схемы, описывающей изменение бронирования."""

    tables_slots: Optional[List[BookingTableSlot]] = Field(None)
    guest_number: Optional[PositiveInt] = Field(None)
    note: Optional[str] = Field(None)
    booking_date: Optional[BookinDateNotPast] = Field(None)
    status: Optional[StatusBooking] = Field(None)


class BookingInfo(BookingBase, FullBaseSchemeDB):
    """Класс схемы, описывающий полные данные о бронировании."""

    user: UserShortInfo
    cafe: CafeShortInfo
    tables_slots: List[BookingTableSlotShortInfo]
    status: StatusBooking
