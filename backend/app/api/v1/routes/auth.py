from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, _get_settings, get_db
from app.core.config import Settings
from app.core.security import get_current_user
from app.models.user import SysPermission, sys_role_permission, sys_user_role
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserMeResponse,
)
from app.schemas.response import ApiResponse, ok
from app.services.auth import (
    authenticate_user,
    change_own_password,
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
    settings: Settings = Depends(_get_settings),
) -> ApiResponse[TokenResponse]:
    access, refresh = refresh_access_token(settings, body.refresh_token)
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
    perm_codes = db.scalars(
        select(SysPermission.code)
        .join(sys_role_permission, SysPermission.id == sys_role_permission.c.permission_id)
        .join(sys_user_role, sys_role_permission.c.role_id == sys_user_role.c.role_id)
        .where(sys_user_role.c.user_id == user.id)
    ).all()
    return ok(UserMeResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        permissions=list(perm_codes),
    ))


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
    _user: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    reset_user_password(db, body.user_id, body.new_password)
    db.commit()
    return ok(message="密码重置成功")
