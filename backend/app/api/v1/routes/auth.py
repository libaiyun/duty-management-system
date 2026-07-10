from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings
from app.core.security import get_current_user
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserMeResponse,
)
from app.schemas.response import ApiResponse, ok
from app.services.auth import authenticate_user, issue_tokens, refresh_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


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
    return ok(UserMeResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
    ))
