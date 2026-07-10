from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, NotFoundError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import SysUser


def authenticate_user(db: Session, username: str, password: str) -> SysUser:
    user = db.scalar(select(SysUser).where(SysUser.username == username))
    if user is None:
        raise UnauthorizedError(message="账号或密码错误")
    if user.status == "locked":
        raise UnauthorizedError(message="账号已被锁定")
    if user.status != "enabled":
        raise UnauthorizedError(message="账号已停用")
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError(message="账号或密码错误")
    return user


def create_user(db: Session, username: str, password: str, display_name: str) -> SysUser:
    user = SysUser(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.flush()
    return user


def issue_tokens(settings: Settings, user: SysUser) -> tuple[str, str]:
    access = create_access_token(settings, user.id, user.username)
    refresh = create_refresh_token(settings, user.id, user.username)
    return access, refresh


def refresh_access_token(settings: Settings, token: str) -> tuple[str, str]:
    payload = decode_token(settings, token)
    if payload.get("type") != "refresh":
        raise UnauthorizedError(message="仅支持 refresh token 刷新")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError()
    return (
        create_access_token(settings, int(user_id_str), payload.get("username", "")),
        create_refresh_token(settings, int(user_id_str), payload.get("username", "")),
    )


def change_own_password(db: Session, user: SysUser, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise BusinessRuleError(message="原密码错误")
    if old_password == new_password:
        raise BusinessRuleError(message="新密码不能与原密码相同")
    user.password_hash = hash_password(new_password)
    db.flush()


def reset_user_password(db: Session, user_id: int, new_password: str) -> None:
    user = db.get(SysUser, user_id)
    if user is None:
        raise NotFoundError(message="用户不存在或已注销")
    user.password_hash = hash_password(new_password)
    db.flush()
