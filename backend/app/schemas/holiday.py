from datetime import date

from pydantic import BaseModel, Field


class HolidayCreateRequest(BaseModel):
    holiday_date: date
    holiday_name: str = Field(..., min_length=1, max_length=64)
    is_legal: bool = True
    remark: str | None = Field(None, max_length=255)


class HolidayUpdateRequest(BaseModel):
    holiday_name: str | None = Field(None, min_length=1, max_length=64)
    is_legal: bool | None = None
    status: str | None = None
    remark: str | None = Field(None, max_length=255)


class HolidayImportRequest(BaseModel):
    items: list[HolidayCreateRequest] = Field(..., min_length=1)


class HolidayResponse(BaseModel):
    id: int
    holiday_date: date
    holiday_name: str
    year: int
    is_legal: bool
    status: str
    remark: str | None = None

    model_config = {"from_attributes": True}


class HolidayImportResponse(BaseModel):
    created: int
    skipped: int
    skipped_dates: list[date] = Field(default_factory=list)


class SubsidyStandardResponse(BaseModel):
    early_meal: int
    middle_meal: int
    night_meal: int
    meal_refund_night_to_middle: int
    holiday_overtime: int
    holiday_overtime_refund_night_to_middle: int
