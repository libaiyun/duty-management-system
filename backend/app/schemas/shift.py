from datetime import date as date_type

from pydantic import BaseModel, Field


class ShiftDefCreateRequest(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=64, pattern=r"^[a-z_]+$")
    name: str = Field(..., min_length=1, max_length=64)
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    display_order: int = 0


class ShiftDefUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    start_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    display_order: int | None = None
    status: str | None = None


class ShiftDefResponse(BaseModel):
    id: int
    org_unit_id: int
    code: str
    name: str
    start_time: str
    end_time: str
    display_order: int
    status: str

    model_config = {"from_attributes": True}


class ShiftRuleCellRequest(BaseModel):
    shift_def_id: int
    person_ids: list[int]


class ShiftRuleDayRequest(BaseModel):
    day_no: int = Field(..., ge=1)
    cells: list[ShiftRuleCellRequest]


class ShiftRuleCreateRequest(BaseModel):
    org_unit_id: int | None = None
    code: str | None = Field(None, min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1, max_length=128)
    cycle_days: int = Field(6, ge=1)
    start_date: date_type
    persons_per_cell: int = Field(2, ge=1)
    remark: str | None = None
    days: list[ShiftRuleDayRequest] = Field(default_factory=list)


class ShiftRuleUpdateRequest(BaseModel):
    org_unit_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=128)
    cycle_days: int | None = Field(None, ge=1)
    start_date: date_type | None = None
    persons_per_cell: int | None = Field(None, ge=1)
    remark: str | None = None
    days: list[ShiftRuleDayRequest] | None = None


class ShiftRuleItemResponse(BaseModel):
    id: int
    day_no: int
    cell_persons: dict

    model_config = {"from_attributes": True}


class ShiftRuleVersionResponse(BaseModel):
    id: int
    version_no: int
    cycle_days: int
    start_date: str
    persons_per_cell: int
    status: str
    snapshot: dict

    model_config = {"from_attributes": True}


class ShiftRuleResponse(BaseModel):
    id: int
    org_unit_id: int | None = None
    code: str
    name: str
    cycle_days: int
    start_date: str
    persons_per_cell: int
    status: str
    remark: str | None = None
    latest_version_id: int | None = None
    latest_version_status: str | None = None
    items: list[ShiftRuleItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ShiftRulePublishResponse(BaseModel):
    id: int
    status: str
    message: str
