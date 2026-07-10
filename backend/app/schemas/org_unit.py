from pydantic import BaseModel, Field


class OrgUnitCreateRequest(BaseModel):
    parent_id: int | None = None
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., min_length=1, max_length=32)
    sort_order: int = 0


class OrgUnitUpdateRequest(BaseModel):
    parent_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=128)
    status: str | None = None
    sort_order: int | None = None


class OrgUnitResponse(BaseModel):
    id: int
    parent_id: int | None = None
    code: str
    name: str
    type: str
    manager_person_id: int | None = None
    status: str
    sort_order: int

    model_config = {"from_attributes": True}


class OrgUnitTreeNode(OrgUnitResponse):
    children: list["OrgUnitTreeNode"] = Field(default_factory=list)
