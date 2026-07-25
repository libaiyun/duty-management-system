from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=64)
    person_id: int | None = None
    role_ids: list[int] = Field(default_factory=list)
    direct_permission_ids: list[int] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=64)
    status: Literal["enabled", "disabled"] | None = None
    person_id: int | None = None


class UserRoleAssignRequest(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    person_id: int | None = None
    status: str
    last_login_at: datetime | None = None
    is_superuser: bool = False

    model_config = {"from_attributes": True}


class UserDetailResponse(UserResponse):
    role_ids: list[int] = Field(default_factory=list)
    direct_permission_ids: list[int] = Field(default_factory=list)
    effective_permission_codes: list[str] = Field(default_factory=list)
    permission_sources: dict[str, list[str]] = Field(default_factory=dict)


class UserPermissionAssignRequest(BaseModel):
    permission_ids: list[int] = Field(default_factory=list)
