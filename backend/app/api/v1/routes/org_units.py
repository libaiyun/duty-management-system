from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.core.exceptions import NotFoundError, StateConflictError
from app.models.organization import OrgUnit
from app.models.user import SysUser
from app.schemas.org_unit import (
    OrgUnitCreateRequest,
    OrgUnitResponse,
    OrgUnitTreeNode,
    OrgUnitUpdateRequest,
)
from app.schemas.response import ApiResponse, ok
from app.services.auth import (
    check_org_unit_referenced,
    create_org_unit,
    list_org_units,
    resolve_scoped_org_unit_ids,
    update_org_unit,
)

router = APIRouter(prefix="/org-units", tags=["org-units"])


def _build_tree(units: list[OrgUnit], parent_id: int | None) -> list[OrgUnitTreeNode]:
    present_ids = {u.id for u in units}
    result: list[OrgUnitTreeNode] = []
    for unit in units:
        # 根节点：显式匹配 parent_id，或其父级不在可见集合内（数据范围裁剪后）
        is_root = unit.parent_id == parent_id or (
            parent_id is None and unit.parent_id is not None and unit.parent_id not in present_ids
        )
        if not is_root:
            continue
        node = OrgUnitTreeNode(
            id=unit.id,
            parent_id=unit.parent_id,
            code=unit.code,
            name=unit.name,
            type=unit.type,
            manager_person_id=unit.manager_person_id,
            status=unit.status,
            sort_order=unit.sort_order,
            children=_build_tree(units, unit.id),
        )
        result.append(node)
    return result


@router.get("", response_model=ApiResponse[list[OrgUnitResponse]])
def get_org_units(
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("org:unit:view")),
) -> ApiResponse[list[OrgUnitResponse]]:
    scoped_ids = resolve_scoped_org_unit_ids(db, user)
    units = list_org_units(db, org_unit_ids=scoped_ids)
    return ok([OrgUnitResponse.model_validate(u) for u in units])


@router.get("/tree", response_model=ApiResponse[list[OrgUnitTreeNode]])
def get_org_tree(
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("org:unit:view")),
) -> ApiResponse[list[OrgUnitTreeNode]]:
    scoped_ids = resolve_scoped_org_unit_ids(db, user)
    units = list_org_units(db, org_unit_ids=scoped_ids)
    return ok(_build_tree(units, None))


@router.post("", response_model=ApiResponse[OrgUnitResponse])
def create_org_unit_endpoint(
    body: OrgUnitCreateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("org:unit:view")),
) -> ApiResponse[OrgUnitResponse]:
    unit = create_org_unit(
        db, body.code, body.name, body.type,
        parent_id=body.parent_id, sort_order=body.sort_order,
        manager_person_id=body.manager_person_id,
    )
    db.commit()
    return ok(OrgUnitResponse.model_validate(unit))


@router.get("/{unit_id}", response_model=ApiResponse[OrgUnitResponse])
def get_org_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("org:unit:view")),
) -> ApiResponse[OrgUnitResponse]:
    unit = db.get(OrgUnit, unit_id)
    if unit is None:
        raise NotFoundError(message="组织不存在")
    return ok(OrgUnitResponse.model_validate(unit))


@router.put("/{unit_id}", response_model=ApiResponse[OrgUnitResponse])
def update_org_unit_endpoint(
    unit_id: int,
    body: OrgUnitUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("org:unit:view")),
) -> ApiResponse[OrgUnitResponse]:
    unit = update_org_unit(
        db, unit_id,
        parent_id=body.parent_id,
        name=body.name,
        status=body.status,
        sort_order=body.sort_order,
        manager_person_id=body.manager_person_id,
        update_manager="manager_person_id" in body.model_fields_set,
    )
    db.commit()
    return ok(OrgUnitResponse.model_validate(unit))


@router.delete("/{unit_id}", response_model=ApiResponse[None])
def delete_org_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("org:unit:view")),
) -> ApiResponse[None]:
    unit = db.get(OrgUnit, unit_id)
    if unit is None:
        raise NotFoundError(message="组织不存在")
    if check_org_unit_referenced(db, unit_id):
        raise StateConflictError(message="当前组织存在下级组织或关联人员，不能删除")
    db.delete(unit)
    db.commit()
    return ok(message="删除成功")
