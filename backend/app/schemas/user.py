from datetime import datetime

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=64)
    person_id: int | None = None


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=64)
    status: str | None = None
    person_id: int | None = None


class UserRoleAssignRequest(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


class UserDataScopeAssignRequest(BaseModel):
    scopes: list["DataScopeItem"] = Field(default_factory=list)


class DataScopeItem(BaseModel):
    scope_type: str
    org_unit_id: int | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    person_id: int | None = None
    status: str
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserDetailResponse(UserResponse):
    role_ids: list[int] = Field(default_factory=list)
    data_scopes: list[DataScopeItem] = Field(default_factory=list)
