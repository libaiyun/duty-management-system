from datetime import date, datetime

from pydantic import BaseModel, Field


class ScheduleResponse(BaseModel):
    id: int
    org_unit_id: int
    org_unit_code: str = ""
    org_unit_name: str = ""
    rule_id: int
    rule_code: str = ""
    rule_name: str = ""
    status: str
    generated_at: datetime | None = None
    published_at: datetime | None = None
    remark: str | None = None
    day_count: int = 0
    shift_count: int = 0
    person_count: int = 0
    coverage_through: date | None = None

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
    change_types: list[str] = []
    effective_change_summary: str | None = None
    pending_change_summary: str | None = None
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


class ScheduleShiftUpdateRequest(BaseModel):
    person_ids: list[int] = Field(min_length=1)
    remark: str | None = Field(default=None, max_length=255)


class HistoricalCorrectionRequest(BaseModel):
    person_ids: list[int] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)


class SchedulePersonOptionResponse(BaseModel):
    id: int
    code: str
    name: str


class DutyChangeLedgerResponse(BaseModel):
    id: int
    duty_date: date
    shift_def_id: int
    shift_def_name: str = ""
    start_at: datetime
    end_at: datetime
    original_person_name: str = ""
    before_person_name: str = ""
    after_person_name: str = ""
    change_type: str
    source_biz_no: str | None = None
    reason: str | None = None
    created_at: datetime
    created_by: int | None = None
    created_by_name: str | None = None
