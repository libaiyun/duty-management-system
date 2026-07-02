from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[dict[str, object]] | None = None
    trace_id: str


def ok(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    return ApiResponse(message=message, data=data)
