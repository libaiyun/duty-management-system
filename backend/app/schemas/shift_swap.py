from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class ShiftSwapCreateRequest(BaseModel):
    swap_type: str = Field(pattern="^(mutual|single_cover)$")
    source_shift_id: int
    target_person_id: int
    target_shift_id: int | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_target_shift(self):
        if self.swap_type == "mutual" and self.target_shift_id is None:
            raise ValueError("互换班次必须选择对方班次")
        if self.swap_type == "single_cover" and self.target_shift_id is not None:
            raise ValueError("单向替班不能填写对方班次")
        return self


class ShiftSwapActionRequest(BaseModel):
    opinion: str | None = Field(default=None, max_length=500)


class ShiftSwapResponse(BaseModel):
    id: int
    biz_no: str
    swap_type: str
    applicant_person_id: int
    applicant_name: str = ""
    source_shift_id: int
    source_duty_date: date | None = None
    target_person_id: int
    target_person_name: str = ""
    target_shift_id: int | None = None
    target_duty_date: date | None = None
    reason: str | None = None
    status: str
    submitted_at: datetime | None = None
    effective_at: datetime | None = None
