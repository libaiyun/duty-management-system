from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.deps import get_page_params
from app.core.exceptions import (
    BadRequestError,
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
    StateConflictError,
    UnauthorizedError,
)
from app.main import create_app
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok


class Item(BaseModel):
    name: str


def build_test_app() -> FastAPI:
    app = create_app()

    @app.get("/test/bad-request")
    def bad_request() -> None:
        raise BadRequestError("参数错误")

    @app.get("/test/unauthorized")
    def unauthorized() -> None:
        raise UnauthorizedError("未登录")

    @app.get("/test/forbidden")
    def forbidden() -> None:
        raise ForbiddenError("无权限")

    @app.get("/test/not-found")
    def not_found() -> None:
        raise NotFoundError("数据不存在")

    @app.get("/test/conflict")
    def conflict() -> None:
        raise StateConflictError("状态冲突")

    @app.get("/test/business-rule")
    def business_rule() -> None:
        raise BusinessRuleError("业务校验失败")

    @app.get("/test/http-not-found")
    def http_not_found() -> None:
        raise HTTPException(status_code=404, detail="HTTP 数据不存在")

    @app.get("/test/http-unauthorized")
    def http_unauthorized() -> None:
        raise HTTPException(
            status_code=401,
            detail="需要登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.get("/test/http-custom-status")
    def http_custom_status() -> None:
        raise HTTPException(status_code=499, detail="custom status")

    @app.get("/test/unexpected")
    def unexpected() -> None:
        raise RuntimeError("boom")

    @app.get("/test/validation")
    def validation(limit: int) -> ApiResponse[int]:
        return ok(limit)

    @app.get("/test/page", response_model=ApiResponse[PageResponse[Item]])
    def page(
        params: PageParams = Depends(get_page_params),
    ) -> ApiResponse[PageResponse[Item]]:
        return ok(
            PageResponse.create(
                items=[Item(name="one")],
                total=21,
                params=params,
            )
        )

    return app


def test_app_exception_handlers_return_unified_error_shape() -> None:
    client = TestClient(build_test_app())
    cases = [
        ("/test/bad-request", 400, "VALIDATION_ERROR"),
        ("/test/unauthorized", 401, "UNAUTHORIZED"),
        ("/test/forbidden", 403, "FORBIDDEN"),
        ("/test/not-found", 404, "NOT_FOUND"),
        ("/test/conflict", 409, "STATE_CONFLICT"),
        ("/test/business-rule", 422, "BUSINESS_RULE_FAILED"),
    ]

    for path, status_code, code in cases:
        response = client.get(path, headers={"X-Trace-Id": "trace-for-test"})
        body = response.json()

        assert response.status_code == status_code
        assert body["code"] == code
        assert body["message"]
        assert body["trace_id"] == "trace-for-test"


def test_http_exception_handler_returns_unified_error_shape() -> None:
    client = TestClient(build_test_app())

    response = client.get("/test/http-not-found", headers={"X-Trace-Id": "trace-404"})

    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "HTTP 数据不存在",
        "trace_id": "trace-404",
    }


def test_http_exception_handler_preserves_headers() -> None:
    client = TestClient(build_test_app())

    response = client.get(
        "/test/http-unauthorized",
        headers={"X-Trace-Id": "trace-401"},
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "code": "UNAUTHORIZED",
        "message": "需要登录",
        "trace_id": "trace-401",
    }


def test_http_exception_handler_accepts_nonstandard_status_code() -> None:
    client = TestClient(build_test_app())

    response = client.get(
        "/test/http-custom-status",
        headers={"X-Trace-Id": "trace-499"},
    )

    assert response.status_code == 499
    assert response.json() == {
        "code": "HTTP_ERROR",
        "message": "custom status",
        "trace_id": "trace-499",
    }


def test_validation_error_handler_returns_details() -> None:
    client = TestClient(build_test_app())

    response = client.get("/test/validation")
    body = response.json()

    assert response.status_code == 400
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "参数校验失败"
    assert body["trace_id"]
    assert body["details"][0]["field"] == "query.limit"


def test_unexpected_exception_handler_returns_500_shape() -> None:
    client = TestClient(build_test_app(), raise_server_exceptions=False)

    response = client.get("/test/unexpected", headers={"X-Trace-Id": "trace-500"})

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "系统繁忙，请稍后重试",
        "trace_id": "trace-500",
    }


def test_pagination_dependency_and_response_model() -> None:
    client = TestClient(build_test_app())

    response = client.get("/test/page?page=2&page_size=10")

    assert response.status_code == 200
    assert response.json() == {
        "code": "OK",
        "message": "success",
        "data": {
            "items": [{"name": "one"}],
            "total": 21,
            "page": 2,
            "page_size": 10,
            "total_pages": 3,
        },
    }


def test_pagination_dependency_rejects_invalid_page() -> None:
    client = TestClient(build_test_app())

    response = client.get("/test/page?page=0")

    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
