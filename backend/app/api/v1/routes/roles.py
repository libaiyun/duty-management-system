from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.schemas.response import ApiResponse, ok
from app.core.role_matrix import CANONICAL_ROLE_CODES
from app.schemas.role import (
    RoleCreateRequest,
    RoleDetailResponse,
    RolePermissionAssignRequest,
    RoleResponse,
    RoleUpdateRequest,
)
from app.core.exceptions import ForbiddenError
from app.services.auth import list_roles

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
    raise ForbiddenError(message="角色矩阵为系统预置，不能创建")


@router.get("/{role_id}", response_model=ApiResponse[RoleDetailResponse])
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[RoleDetailResponse]:
    from app.core.exceptions import NotFoundError
    from app.models.user import SysRole
    role = db.get(SysRole, role_id)
    if role is None or role.code not in CANONICAL_ROLE_CODES:
        raise NotFoundError(message="角色不存在")
    return ok(RoleDetailResponse(
        id=role.id,
        code=role.code,
        name=role.name,
        remark=role.remark,
        status=role.status,
        permission_ids=[p.id for p in role.permissions],
    ))


@router.put("/{role_id}", response_model=ApiResponse[RoleResponse])
def update_role_endpoint(
    role_id: int,
    body: RoleUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[RoleResponse]:
    raise ForbiddenError(message="角色矩阵为系统预置，不能修改")


@router.put("/{role_id}/permissions", response_model=ApiResponse[None])
def update_role_permissions(
    role_id: int,
    body: RolePermissionAssignRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("system:user:manage")),
) -> ApiResponse[None]:
    raise ForbiddenError(message="角色权限为系统预置，不能修改")
