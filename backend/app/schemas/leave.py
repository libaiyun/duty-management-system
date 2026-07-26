from datetime import date, datetime

from pydantic import BaseModel, Field


class LeaveCreateRequest(BaseModel):
    schedule_shift_id: int
    leave_type: str = Field(pattern="^(public|personal|sick)$")
    reason: str | None = Field(default=None, max_length=500)


class LeaveResponse(BaseModel):
    id: int
    biz_no: str
    applicant_person_id: int
    applicant_name: str = ""
    schedule_shift_id: int
    duty_date: date | None = None
    leave_type: str
    reason: str | None = None
    status: str
    cover_status: str | None = None
    cover_assignment_id: int | None = None
    cover_person_id: int | None = None
    cover_person_name: str | None = None
    submitted_at: datetime | None = None


class CoverArrangeRequest(BaseModel):
    cover_person_id: int
    remark: str | None = Field(default=None, max_length=500)


class CoverActionRequest(BaseModel):
    opinion: str | None = Field(default=None, max_length=500)


class CoverCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CoverResponse(BaseModel):
    id: int
    biz_no: str
    leave_request_id: int
    cover_person_id: int | None = None
    cover_person_name: str | None = None
    status: str
    remark: str | None = None
    duty_date: date | None = None
    applicant_name: str = ""
