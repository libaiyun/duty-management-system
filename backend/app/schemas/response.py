from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T | None = None
    trace_id: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object] | list[dict[str, object]] | None = None
    trace_id: str


def ok(
    data: T | None = None,
    message: str = "success",
    trace_id: str | None = None,
) -> ApiResponse[T]:
    return ApiResponse(
        message=message,
        data=data,
        trace_id=trace_id or str(uuid4()),
    )
