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
