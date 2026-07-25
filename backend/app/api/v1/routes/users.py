from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.core.exceptions import NotFoundError
from app.models.user import SysUser
from app.schemas.person import PersonResponse
from app.schemas.response import ApiResponse, ok
from app.schemas.user import (
    UserCreateRequest,
    UserDetailResponse,
    UserPermissionAssignRequest,
    UserResponse,
    UserRoleAssignRequest,
    UserUpdateRequest,
)
from app.services.auth import (
    assign_user_permissions,
    assign_user_roles,
    create_user,
    effective_permission_sources,
    get_user_detail,
    list_persons,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=ApiResponse[list[UserResponse]])
def get_users(
    db: Session = Depends(get_db),
    _perm: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[list[UserResponse]]:
    users = list_users(db)
    return ok([UserResponse.model_validate(u) for u in users])


@router.post("", response_model=ApiResponse[UserResponse])
def create_user_endpoint(
    body: UserCreateRequest,
    db: Session = Depends(get_db),
    actor: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[UserResponse]:
    user = create_user(db, body.username, body.password, body.display_name, body.person_id)
    assign_user_roles(db, user.id, body.role_ids, actor)
    assign_user_permissions(db, user.id, body.direct_permission_ids, actor)
    db.commit()
    return ok(UserResponse.model_validate(user))


@router.get("/persons", response_model=ApiResponse[list[PersonResponse]])
def get_binding_persons(
    db: Session = Depends(get_db),
    _perm: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[list[PersonResponse]]:
    """List every person for global account binding, without room context."""
    persons = list_persons(db)
    return ok([PersonResponse.model_validate(person) for person in persons])


@router.get("/{user_id}", response_model=ApiResponse[UserDetailResponse])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _perm: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[UserDetailResponse]:
    user = get_user_detail(db, user_id)
    if user is None:
        raise NotFoundError(message="用户不存在")
    sources = effective_permission_sources(db, user)
    return ok(UserDetailResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        person_id=user.person_id,
        status=user.status,
        last_login_at=user.last_login_at,
        role_ids=[r.id for r in user.roles],
        direct_permission_ids=[p.id for p in user.direct_permissions],
        effective_permission_codes=sorted(sources),
        permission_sources=sources,
        is_superuser=user.is_superuser,
    ))


@router.put("/{user_id}", response_model=ApiResponse[UserResponse])
def update_user_endpoint(
    user_id: int,
    body: UserUpdateRequest,
    db: Session = Depends(get_db),
    actor: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[UserResponse]:
    update_person = "person_id" in body.model_fields_set
    user = update_user(
        db, user_id, body.display_name, body.status,
        body.person_id, update_person, actor,
    )
    db.commit()
    return ok(UserResponse.model_validate(user))


@router.put("/{user_id}/roles", response_model=ApiResponse[None])
def update_user_roles(
    user_id: int,
    body: UserRoleAssignRequest,
    db: Session = Depends(get_db),
    actor: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    assign_user_roles(db, user_id, body.role_ids, actor)
    db.commit()
    return ok(message="角色分配成功")


@router.put("/{user_id}/permissions", response_model=ApiResponse[None])
def update_user_permissions(
    user_id: int,
    body: UserPermissionAssignRequest,
    db: Session = Depends(get_db),
    actor: SysUser = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    assign_user_permissions(db, user_id, body.permission_ids, actor)
    db.commit()
    return ok(message="账号直接权限分配成功")
