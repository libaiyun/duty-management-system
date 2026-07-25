from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.core.exceptions import NotFoundError
from app.models.user import SysRole
from app.schemas.response import ApiResponse, ok
from app.schemas.role import (
    RoleCreateRequest,
    RoleDetailResponse,
    RolePermissionAssignRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from app.services.auth import assign_role_permissions, create_role, list_roles, update_role

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=ApiResponse[list[RoleResponse]])
def get_roles(
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[list[RoleResponse]]:
    roles = list_roles(db)
    return ok([RoleResponse.model_validate(r) for r in roles])


@router.post("", response_model=ApiResponse[RoleResponse])
def create_role_endpoint(
    body: RoleCreateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[RoleResponse]:
    role = create_role(db, body.code, body.name, body.remark)
    db.commit()
    return ok(RoleResponse.model_validate(role))


@router.get("/{role_id}", response_model=ApiResponse[RoleDetailResponse])
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[RoleDetailResponse]:
    role = db.get(SysRole, role_id)
    if role is None:
        raise NotFoundError(message="角色不存在")
    return ok(RoleDetailResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        remark=role.remark,
        status=role.status,
        permission_ids=[p.id for p in role.permissions],
        user_ids=[u.id for u in role.users],
        is_builtin=role.is_builtin,
    ))


@router.put("/{role_id}", response_model=ApiResponse[RoleResponse])
def update_role_endpoint(
    role_id: int,
    body: RoleUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[RoleResponse]:
    role = update_role(db, role_id, body.name, body.remark, body.status, "remark" in body.model_fields_set)
    db.commit()
    return ok(RoleResponse.model_validate(role))


@router.put("/{role_id}/permissions", response_model=ApiResponse[None])
def update_role_permissions(
    role_id: int,
    body: RolePermissionAssignRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    assign_role_permissions(db, role_id, body.permission_ids)
    db.commit()
    return ok(message="角色权限分配成功")
