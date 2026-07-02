from http import HTTPStatus
from typing import Any


class AppException(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class BadRequestError(AppException):
    def __init__(self, message: str = "参数错误") -> None:
        super().__init__(
            status_code=HTTPStatus.BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=message,
        )


class UnauthorizedError(AppException):
    def __init__(self, message: str = "未登录或登录已过期") -> None:
        super().__init__(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="UNAUTHORIZED",
            message=message,
        )


class ForbiddenError(AppException):
    def __init__(self, message: str = "无权限访问") -> None:
        super().__init__(
            status_code=HTTPStatus.FORBIDDEN,
            code="FORBIDDEN",
            message=message,
        )


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(
            status_code=HTTPStatus.NOT_FOUND,
            code="NOT_FOUND",
            message=message,
        )


class StateConflictError(AppException):
    def __init__(self, message: str = "状态冲突") -> None:
        super().__init__(
            status_code=HTTPStatus.CONFLICT,
            code="STATE_CONFLICT",
            message=message,
        )


class BusinessRuleError(AppException):
    def __init__(self, message: str = "业务校验失败") -> None:
        super().__init__(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="BUSINESS_RULE_FAILED",
            message=message,
        )
