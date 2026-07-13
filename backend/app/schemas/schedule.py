from datetime import date, datetime

from pydantic import BaseModel


class ScheduleResponse(BaseModel):
    id: int
    org_unit_id: int
    org_unit_code: str = ""
    org_unit_name: str = ""
    year_month: str
    rule_id: int
    rule_code: str = ""
    rule_name: str = ""
    status: str
    generated_at: datetime | None = None
    published_at: datetime | None = None
    locked_at: datetime | None = None
    remark: str | None = None
    day_count: int = 0
    shift_count: int = 0
    person_count: int = 0

    model_config = {"from_attributes": True}


class ScheduleShiftPersonResponse(BaseModel):
    id: int
    person_id: int
    person_code: str = ""
    person_name: str = ""
    position_no: int
    source_type: str
    remark: str | None = None

    model_config = {"from_attributes": True}


class ScheduleShiftResponse(BaseModel):
    id: int
    shift_def_id: int
    shift_def_code: str = ""
    shift_def_name: str = ""
    start_at: datetime
    end_at: datetime
    status: str
    persons: list[ScheduleShiftPersonResponse] = []

    model_config = {"from_attributes": True}


class ScheduleDayResponse(BaseModel):
    id: int
    duty_date: date
    weekday: int
    is_legal_holiday: bool
    holiday_name: str | None = None
    shifts: list[ScheduleShiftResponse] = []

    model_config = {"from_attributes": True}
