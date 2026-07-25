from typing import Literal

from pydantic import BaseModel, Field


class RoleCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    remark: str | None = None


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    remark: str | None = None
    status: Literal["enabled", "disabled"] | None = None


class RolePermissionAssignRequest(BaseModel):
    permission_ids: list[int] = Field(default_factory=list)


class RoleResponse(BaseModel):
    id: int
    code: str
    name: str
    remark: str | None = None
    status: str
    is_builtin: bool = False

    model_config = {"from_attributes": True}


class RoleDetailResponse(RoleResponse):
    permission_ids: list[int] = Field(default_factory=list)
    user_ids: list[int] = Field(default_factory=list)
