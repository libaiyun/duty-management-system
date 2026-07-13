from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db
from app.core.exceptions import NotFoundError
from app.schemas.response import ApiResponse, ok
from app.schemas.shift import (
    ShiftRuleCreateRequest,
    ShiftRuleResponse,
    ShiftRuleUpdateRequest,
)
from app.services.auth import (
    create_shift_rule,
    delete_shift_rule,
    get_shift_rule,
    list_shift_rules,
    update_shift_rule,
)

router = APIRouter(prefix="/shift-rules", tags=["shift-rules"])


@router.get("", response_model=ApiResponse[list[ShiftRuleResponse]])
def get_shift_rules(
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[list[ShiftRuleResponse]]:
    rules = list_shift_rules(db)
    return ok([ShiftRuleResponse.model_validate(r) for r in rules])


@router.post("", response_model=ApiResponse[ShiftRuleResponse])
def create_shift_rule_endpoint(
    body: ShiftRuleCreateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[ShiftRuleResponse]:
    rule = create_shift_rule(
        db, body.code, body.name, body.station_type,
        persons_per_shift=body.persons_per_shift,
        rule_type=body.rule_type,
        org_unit_id=body.org_unit_id,
        remark=body.remark,
        items=[item.model_dump() for item in body.items],
    )
    db.commit()
    return ok(ShiftRuleResponse.model_validate(rule))


@router.get("/{rule_id}", response_model=ApiResponse[ShiftRuleResponse])
def get_shift_rule_endpoint(
    rule_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[ShiftRuleResponse]:
    rule = get_shift_rule(db, rule_id)
    if rule is None:
        raise NotFoundError(message="排班规则不存在")
    return ok(ShiftRuleResponse.model_validate(rule))


@router.put("/{rule_id}", response_model=ApiResponse[ShiftRuleResponse])
def update_shift_rule_endpoint(
    rule_id: int,
    body: ShiftRuleUpdateRequest,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[ShiftRuleResponse]:
    rule = update_shift_rule(
        db, rule_id,
        name=body.name,
        station_type=body.station_type,
        persons_per_shift=body.persons_per_shift,
        rule_type=body.rule_type,
        status=body.status,
        org_unit_id=body.org_unit_id,
        remark=body.remark,
        items=[item.model_dump() for item in body.items] if body.items is not None else None,
    )
    db.commit()
    return ok(ShiftRuleResponse.model_validate(rule))


@router.delete("/{rule_id}", response_model=ApiResponse[None])
def delete_shift_rule_endpoint(
    rule_id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("shift:rule:view")),
) -> ApiResponse[None]:
    delete_shift_rule(db, rule_id)
    db.commit()
    return ok(message="删除成功")
