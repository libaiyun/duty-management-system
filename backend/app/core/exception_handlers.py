from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.schemas.response import ErrorResponse

HTTP_ERROR_CODES = {
    HTTPStatus.BAD_REQUEST: "VALIDATION_ERROR",
    HTTPStatus.UNAUTHORIZED: "UNAUTHORIZED",
    HTTPStatus.FORBIDDEN: "FORBIDDEN",
    HTTPStatus.NOT_FOUND: "NOT_FOUND",
    HTTPStatus.CONFLICT: "STATE_CONFLICT",
    HTTPStatus.UNPROCESSABLE_ENTITY: "BUSINESS_RULE_FAILED",
}


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, handle_app_exception)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_exception)


async def handle_app_exception(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        request=request,
    )


async def handle_http_exception(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=_http_error_code(exc.status_code),
        message=_detail_to_message(exc.detail),
        request=request,
        headers=exc.headers,
    )


async def handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return _error_response(
        status_code=HTTPStatus.BAD_REQUEST,
        code="VALIDATION_ERROR",
        message="参数校验失败",
        details=details,
        request=request,
    )


async def handle_unexpected_exception(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return _error_response(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="系统繁忙，请稍后重试",
        request=request,
    )


def _error_response(
    *,
    status_code: int | HTTPStatus,
    code: str,
    message: str,
    request: Request,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = ErrorResponse(
        code=code,
        message=message,
        details=details,
        trace_id=_get_trace_id(request),
    )
    return JSONResponse(
        status_code=int(status_code),
        content=response.model_dump(exclude_none=True),
        headers=headers,
    )


def _detail_to_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    return "请求处理失败"


def _http_error_code(status_code: int) -> str:
    try:
        status = HTTPStatus(status_code)
    except ValueError:
        return "HTTP_ERROR"
    return HTTP_ERROR_CODES.get(status, "HTTP_ERROR")


def _get_trace_id(request: Request) -> str:
    trace_id = request.headers.get("X-Trace-Id")
    if trace_id:
        return trace_id
    return str(uuid4())
