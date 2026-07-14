from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class UserMeResponse(BaseModel):
    id: int
    username: str
    display_name: str
    status: str
    permissions: list[str] = Field(default_factory=list)
    person_id: int | None = None
    room_id: int | None = None
    room_name: str | None = None
    can_switch_room: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


class ResetPasswordRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    new_password: str = Field(..., min_length=1, max_length=128)
