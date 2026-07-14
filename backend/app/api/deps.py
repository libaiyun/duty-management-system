from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, CurrentRoomRequiredError, ForbiddenError
from app.core.security import get_current_user
from app.db.session import get_db  # noqa: F401 — re-exported for route dependencies
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.user import SysUser
from app.schemas.pagination import PageParams
from app.services.auth import check_user_permission, has_global_scope, resolve_user_data_scopes


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


def resolve_current_room_id(request: Request, db: Session, user: SysUser) -> int:
    """Return the room selected by an administrator or bound to a normal user."""
    scopes = resolve_user_data_scopes(db, user)
    if has_global_scope(scopes):
        header_value = request.headers.get("X-Current-Room-Id")
        if not header_value:
            raise CurrentRoomRequiredError()
        try:
            room_id = int(header_value)
        except ValueError as exc:
            raise BusinessRuleError(message="当前机房不合法") from exc
        room = db.get(OrgUnit, room_id)
        if room is None or room.type != "room":
            raise BusinessRuleError(message="当前机房不合法")
        return room_id

    person = db.get(Person, user.person_id) if user.person_id is not None else None
    if person is None or person.org_unit_id is None:
        raise BusinessRuleError(message="当前账号未绑定所属机房的人员")
    return person.org_unit_id
