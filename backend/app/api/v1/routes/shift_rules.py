from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db, resolve_current_room_id
from app.models.user import SysUser
from app.core.exceptions import NotFoundError
from app.schemas.response import ApiResponse, ok
from app.schemas.shift import (
    ShiftRuleCreateRequest,
    ShiftRuleItemResponse,
    ShiftRulePublishResponse,
    ShiftRuleResponse,
    ShiftRuleUpdateRequest,
    ShiftRuleVersionResponse,
)
from app.services.auth import (
    create_shift_rule,
    delete_shift_rule,
    get_rule_latest_items,
    get_shift_rule,
    list_shift_rules,
    publish_shift_rule,
    update_shift_rule,
)

router = APIRouter(prefix="/shift-rules", tags=["shift-rules"])


@router.get("", response_model=ApiResponse[list[ShiftRuleResponse]])
def get_shift_rules(
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[list[ShiftRuleResponse]]:
    room_id = resolve_current_room_id(request, db, user)
    rules = list_shift_rules(db, room_id)
    result = []
    for r in rules:
        resp = ShiftRuleResponse.model_validate(r)
        latest = get_rule_latest_items(db, int(r.id))  # type: ignore[arg-type]
        resp.items = [ShiftRuleItemResponse.model_validate(i) for i in latest]
        result.append(resp)
    return ok(result)


@router.post("", response_model=ApiResponse[ShiftRuleResponse])
def create_shift_rule_endpoint(
    request: Request,
    body: ShiftRuleCreateRequest,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:rule:manage")),
) -> ApiResponse[ShiftRuleResponse]:
    room_id = resolve_current_room_id(request, db, user)
    rule = create_shift_rule(
        db, body.code, body.name,
        cycle_days=body.cycle_days,
        start_date=body.start_date.isoformat(),
        persons_per_cell=body.persons_per_cell,
        org_unit_id=room_id,
        remark=body.remark,
        days=[d.model_dump() for d in body.days],
    )
    db.commit()
    resp = ShiftRuleResponse.model_validate(rule)
    items = get_rule_latest_items(db, int(rule.id))  # type: ignore[arg-type]
    resp.items = [ShiftRuleItemResponse.model_validate(i) for i in items]
    return ok(resp)


@router.get("/{rule_id}", response_model=ApiResponse[ShiftRuleResponse])
def get_shift_rule_endpoint(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[ShiftRuleResponse]:
    room_id = resolve_current_room_id(request, db, user)
    rule = get_shift_rule(db, rule_id, room_id)
    if rule is None:
        raise NotFoundError(message="排班规则不存在")
    resp = ShiftRuleResponse.model_validate(rule)
    items = get_rule_latest_items(db, rule_id)
    resp.items = [ShiftRuleItemResponse.model_validate(i) for i in items]
    return ok(resp)


@router.put("/{rule_id}", response_model=ApiResponse[ShiftRuleResponse])
def update_shift_rule_endpoint(
    rule_id: int,
    request: Request,
    body: ShiftRuleUpdateRequest,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:rule:manage")),
) -> ApiResponse[ShiftRuleResponse]:
    room_id = resolve_current_room_id(request, db, user)
    if get_shift_rule(db, rule_id, room_id) is None:
        raise NotFoundError(message="排班规则不存在")
    rule = update_shift_rule(
        db, rule_id,
        name=body.name,
        cycle_days=body.cycle_days,
        start_date=body.start_date.isoformat() if body.start_date else None,
        persons_per_cell=body.persons_per_cell,
        org_unit_id=room_id,
        remark=body.remark,
        days=[d.model_dump() for d in body.days] if body.days is not None else None,
    )
    db.commit()
    resp = ShiftRuleResponse.model_validate(rule)
    items = get_rule_latest_items(db, rule_id)
    resp.items = [ShiftRuleItemResponse.model_validate(i) for i in items]
    return ok(resp)


@router.delete("/{rule_id}", response_model=ApiResponse[None])
def delete_shift_rule_endpoint(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:rule:manage")),
) -> ApiResponse[None]:
    if get_shift_rule(db, rule_id, resolve_current_room_id(request, db, user)) is None:
        raise NotFoundError(message="排班规则不存在")
    delete_shift_rule(db, rule_id)
    db.commit()
    return ok(message="删除成功")


@router.post("/{rule_id}/publish", response_model=ApiResponse[ShiftRulePublishResponse])
def publish_shift_rule_endpoint(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:rule:manage")),
) -> ApiResponse[ShiftRulePublishResponse]:
    if get_shift_rule(db, rule_id, resolve_current_room_id(request, db, user)) is None:
        raise NotFoundError(message="排班规则不存在")
    rule = publish_shift_rule(db, rule_id)
    db.commit()
    return ok(ShiftRulePublishResponse(
        id=int(rule.id),  # type: ignore[arg-type]
        status=rule.status,
        message="规则已发布，排班生成中",
    ))


@router.get("/{rule_id}/versions", response_model=ApiResponse[list[ShiftRuleVersionResponse]])
def get_rule_versions(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[list[ShiftRuleVersionResponse]]:
    from app.models.shift import ShiftRuleVersion
    from sqlalchemy import select

    if get_shift_rule(db, rule_id, resolve_current_room_id(request, db, user)) is None:
        raise NotFoundError(message="排班规则不存在")
    versions = list(db.scalars(
        select(ShiftRuleVersion)
        .where(ShiftRuleVersion.rule_id == rule_id)
        .order_by(ShiftRuleVersion.version_no.desc())
    ).all())
    return ok([ShiftRuleVersionResponse.model_validate(v) for v in versions])
