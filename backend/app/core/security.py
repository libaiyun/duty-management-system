from datetime import datetime, timedelta, timezone

from bcrypt import checkpw, gensalt, hashpw
from fastapi import Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.models.user import SysUser


def hash_password(password: str) -> str:
    return hashpw(password.encode("utf-8"), gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(settings: Settings, user_id: int, username: str, token_type: str, expire_minutes: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)  # type: ignore[no-any-return]


def create_access_token(settings: Settings, user_id: int, username: str) -> str:
    return _create_token(settings, user_id, username, "access", settings.jwt_access_token_expire_minutes)


def create_refresh_token(settings: Settings, user_id: int, username: str) -> str:
    return _create_token(settings, user_id, username, "refresh", settings.jwt_refresh_token_expire_minutes)


def decode_token(settings: Settings, token: str) -> dict:
    try:
        return jwt.decode(  # type: ignore[no-any-return]
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise UnauthorizedError(message="登录已过期，请重新登录") from None


def get_current_user(settings: Settings, request: Request, db: Session) -> SysUser:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError()
    token = auth_header[len("Bearer "):]
    payload = decode_token(settings, token)
    if payload.get("type") != "access":
        raise UnauthorizedError(message="无效的 token 类型")
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError()
    user = db.get(SysUser, int(user_id_str))
    if user is None:
        raise UnauthorizedError(message="用户不存在或已注销")
    if user.status != "enabled":
        raise UnauthorizedError(message="账号已停用")
    return user
