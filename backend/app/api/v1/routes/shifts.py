from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db, resolve_current_room_id
from app.core.exceptions import NotFoundError
from app.models.shift import ShiftDef
from app.models.user import SysUser
from app.schemas.response import ApiResponse, ok
from app.schemas.shift import ShiftDefCreateRequest, ShiftDefResponse, ShiftDefUpdateRequest
from app.services.auth import create_shift_def, list_shift_defs, update_shift_def

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.get("", response_model=ApiResponse[list[ShiftDefResponse]])
def get_shift_defs(
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:def:view")),
) -> ApiResponse[list[ShiftDefResponse]]:
    defs = list_shift_defs(db, resolve_current_room_id(request, db, user))
    return ok([ShiftDefResponse.model_validate(d) for d in defs])


@router.post("", response_model=ApiResponse[ShiftDefResponse])
def create_shift_def_endpoint(
    body: ShiftDefCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:def:manage")),
) -> ApiResponse[ShiftDefResponse]:
    sd = create_shift_def(
        db, resolve_current_room_id(request, db, user), body.code, body.name,
        body.start_time, body.end_time,
        display_order=body.display_order,
    )
    db.commit()
    return ok(ShiftDefResponse.model_validate(sd))


@router.get("/{shift_id}", response_model=ApiResponse[ShiftDefResponse])
def get_shift_def(
    shift_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:def:view")),
) -> ApiResponse[ShiftDefResponse]:
    sd = db.get(ShiftDef, shift_id)
    if sd is None:
        raise NotFoundError(message="班次不存在")
    if sd.org_unit_id != resolve_current_room_id(request, db, user):
        raise NotFoundError(message="班次不存在")
    return ok(ShiftDefResponse.model_validate(sd))


@router.put("/{shift_id}", response_model=ApiResponse[ShiftDefResponse])
def update_shift_def_endpoint(
    shift_id: int,
    body: ShiftDefUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("shift:def:manage")),
) -> ApiResponse[ShiftDefResponse]:
    shift_def = db.get(ShiftDef, shift_id)
    if shift_def is None or shift_def.org_unit_id != resolve_current_room_id(request, db, user):
        raise NotFoundError(message="班次不存在")
    sd = update_shift_def(
        db, shift_id,
        name=body.name,
        start_time=body.start_time,
        end_time=body.end_time,
        display_order=body.display_order,
        status=body.status,
    )
    db.commit()
    return ok(ShiftDefResponse.model_validate(sd))
