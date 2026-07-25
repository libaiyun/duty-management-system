from typing import Literal

from pydantic import BaseModel, Field

PersonType = Literal["duty_operator", "maintenance", "room_director", "deputy_director"]


class PersonCreateRequest(BaseModel):
    org_unit_id: int | None = None
    code: str | None = Field(None, min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=64)
    person_type: PersonType
    phone: str | None = None
    participate_schedule: bool = False
    remark: str | None = None


class PersonUpdateRequest(BaseModel):
    org_unit_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=64)
    person_type: PersonType | None = None
    phone: str | None = None
    participate_schedule: bool | None = None
    status: str | None = None
    remark: str | None = None


class PersonResponse(BaseModel):
    id: int
    org_unit_id: int | None = None
    code: str
    name: str
    person_type: str
    phone: str | None = None
    participate_schedule: bool
    status: str
    remark: str | None = None
    account_bound: bool
    account_username: str | None = None

    model_config = {"from_attributes": True}
