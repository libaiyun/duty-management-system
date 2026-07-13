from pydantic import BaseModel, Field


class ShiftDefCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z_]+$")
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
    code: str
    name: str
    start_time: str
    end_time: str
    display_order: int
    status: str

    model_config = {"from_attributes": True}


class ShiftRuleItemRequest(BaseModel):
    group_type: str = Field(..., min_length=1, max_length=32)
    sequence_no: int = 0
    shift_code: str = Field(..., min_length=1, max_length=32)
    repeat_count: int = Field(1, ge=1)
    remark: str | None = Field(None, max_length=255)


class ShiftRuleCreateRequest(BaseModel):
    org_unit_id: int | None = None
    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1, max_length=128)
    station_type: str = Field(..., min_length=1, max_length=64)
    persons_per_shift: int = Field(2, ge=1)
    rule_type: str = Field("broadcast_fixed", min_length=1, max_length=32)
    remark: str | None = None
    items: list[ShiftRuleItemRequest] = Field(default_factory=list)


class ShiftRuleUpdateRequest(BaseModel):
    org_unit_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=128)
    station_type: str | None = Field(None, min_length=1, max_length=64)
    persons_per_shift: int | None = Field(None, ge=1)
    rule_type: str | None = Field(None, min_length=1, max_length=32)
    status: str | None = None
    remark: str | None = None
    items: list[ShiftRuleItemRequest] | None = None


class ShiftRuleItemResponse(BaseModel):
    id: int
    group_type: str
    sequence_no: int
    shift_code: str
    repeat_count: int
    remark: str | None = None

    model_config = {"from_attributes": True}


class ShiftRuleResponse(BaseModel):
    id: int
    org_unit_id: int | None = None
    code: str
    name: str
    station_type: str
    persons_per_shift: int
    rule_type: str
    status: str
    remark: str | None = None
    items: list[ShiftRuleItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
