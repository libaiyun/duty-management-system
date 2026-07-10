from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.core.security import get_current_user
from app.db.session import get_db  # noqa: F401 — re-exported for route dependencies
from app.models.user import SysUser
from app.schemas.pagination import PageParams
from app.services.auth import check_user_permission


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


class RequirePermission:
    def __init__(self, permission_code: str) -> None:
        self.permission_code = permission_code

    def __call__(
        self,
        request: Request,
        db: Session = Depends(get_db),
        settings: Settings = Depends(_get_settings),
    ) -> SysUser:
        user = get_current_user(settings, request, db)
        if not check_user_permission(db, user, self.permission_code):
            raise ForbiddenError(message=f"缺少权限: {self.permission_code}")
        return user


def get_page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)
