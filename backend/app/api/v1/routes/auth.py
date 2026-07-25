from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, _get_settings, get_db
from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.core.security import get_current_user
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.user import SysUser
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    RoomContextResponse,
    TokenResponse,
    UserMeResponse,
)
from app.schemas.response import ApiResponse, ok
from app.services.auth import (
    authenticate_user,
    change_own_password,
    effective_permission_sources,
    is_room_switching_account,
    issue_tokens,
    refresh_access_token,
    reset_user_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_get_settings),
) -> ApiResponse[TokenResponse]:
    user = authenticate_user(db, body.username, body.password)
    user.last_login_at = datetime.now(UTC)
    db.commit()
    access, refresh = issue_tokens(settings, user)
    return ok(TokenResponse(access_token=access, refresh_token=refresh))


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_get_settings),
) -> ApiResponse[TokenResponse]:
    access, refresh = refresh_access_token(db, settings, body.refresh_token)
    return ok(TokenResponse(access_token=access, refresh_token=refresh))


@router.post("/logout", response_model=ApiResponse[None])
def logout() -> ApiResponse[None]:
    return ok(message="已退出登录")


@router.get("/me", response_model=ApiResponse[UserMeResponse])
def me(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_get_settings),
) -> ApiResponse[UserMeResponse]:
    user = get_current_user(settings, request, db)
    perm_codes = sorted(effective_permission_sources(db, user))
    can_switch_room = is_room_switching_account(user)
    person = db.get(Person, user.person_id) if user.person_id is not None else None
    room = person.org_unit if person is not None else None
    return ok(UserMeResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        permissions=list(perm_codes),
        person_id=user.person_id,
        person_status=person.status if person is not None else None,
        person_type=person.person_type if person is not None else None,
        participate_schedule=bool(person and person.participate_schedule),
        room_id=room.id if room is not None and not can_switch_room else None,
        room_name=room.name if room is not None and not can_switch_room else None,
        can_switch_room=can_switch_room,
        is_superuser=user.is_superuser,
    ))


@router.get("/rooms", response_model=ApiResponse[list[RoomContextResponse]])
def room_contexts(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_get_settings),
) -> ApiResponse[list[RoomContextResponse]]:
    """List selectable rooms without granting organization-management access."""
    user = get_current_user(settings, request, db)
    if not is_room_switching_account(user):
        raise ForbiddenError(message="当前账号不能切换机房")
    rooms = db.scalars(
        select(OrgUnit)
        .where(OrgUnit.type == "room", OrgUnit.status == "enabled")
        .order_by(OrgUnit.sort_order, OrgUnit.id)
    ).all()
    return ok([
        RoomContextResponse(id=room.id, code=room.code, name=room.name)
        for room in rooms
    ])


@router.put("/password", response_model=ApiResponse[None])
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_get_settings),
) -> ApiResponse[None]:
    user = get_current_user(settings, request, db)
    change_own_password(db, user, body.old_password, body.new_password)
    db.commit()
    return ok(message="密码修改成功")


@router.post("/password/reset", response_model=ApiResponse[None])
def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    actor: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    reset_user_password(db, body.user_id, body.new_password, actor)
    db.commit()
    return ok(message="密码重置成功")
