from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.core.exceptions import NotFoundError
from app.models.user import SysDataScope
from app.schemas.response import ApiResponse, ok
from app.schemas.user import (
    DataScopeItem,
    UserCreateRequest,
    UserDataScopeAssignRequest,
    UserDetailResponse,
    UserResponse,
    UserRoleAssignRequest,
    UserUpdateRequest,
)
from app.services.auth import (
    assign_user_data_scopes,
    assign_user_roles,
    create_user,
    get_user_detail,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=ApiResponse[list[UserResponse]])
def get_users(
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[list[UserResponse]]:
    users = list_users(db)
    return ok([UserResponse.model_validate(u) for u in users])


@router.post("", response_model=ApiResponse[UserResponse])
def create_user_endpoint(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[UserResponse]:
    user = create_user(db, body.username, body.password, body.display_name)
    db.commit()
    return ok(UserResponse.model_validate(user))


@router.get("/{user_id}", response_model=ApiResponse[UserDetailResponse])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[UserDetailResponse]:
    user = get_user_detail(db, user_id)
    if user is None:
        raise NotFoundError(message="用户不存在")
    scopes = db.scalars(select(SysDataScope).where(SysDataScope.user_id == user_id)).all()
    scope_items = [DataScopeItem(scope_type=s.scope_type, org_unit_id=s.org_unit_id) for s in scopes]
    return ok(UserDetailResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        person_id=user.person_id,
        status=user.status,
        last_login_at=user.last_login_at,
        role_ids=[r.id for r in user.roles],
        data_scopes=scope_items,
    ))


@router.put("/{user_id}", response_model=ApiResponse[UserResponse])
def update_user_endpoint(
    user_id: int,
    body: UserUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[UserResponse]:
    user = update_user(db, user_id, body.display_name, body.status)
    db.commit()
    return ok(UserResponse.model_validate(user))


@router.put("/{user_id}/roles", response_model=ApiResponse[None])
def update_user_roles(
    user_id: int,
    body: UserRoleAssignRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    assign_user_roles(db, user_id, body.role_ids)
    db.commit()
    return ok(message="角色分配成功")


@router.put("/{user_id}/data-scopes", response_model=ApiResponse[None])
def update_user_data_scopes(
    user_id: int,
    body: UserDataScopeAssignRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    scopes = [(s.scope_type, s.org_unit_id) for s in body.scopes]
    assign_user_data_scopes(db, user_id, scopes)
    db.commit()
    return ok(message="数据范围设置成功")
