from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import RequirePermission, get_db, get_page_params, resolve_current_room_id
from app.core.exceptions import ForbiddenError
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson, ShiftSwap
from app.models.shift import ShiftDef
from app.models.user import SysUser
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.schemas.shift_swap import ShiftSwapActionRequest, ShiftSwapCreateRequest, ShiftSwapResponse
from app.services.shift_swap import create_swap, get_swap, target_confirm, withdraw_or_cancel

router = APIRouter(prefix="/shift-swaps", tags=["shift-swaps"])


def _response(swap: ShiftSwap) -> ShiftSwapResponse:
    return ShiftSwapResponse(id=swap.id, biz_no=swap.biz_no, swap_type=swap.swap_type, applicant_person_id=swap.applicant_person_id, applicant_name=swap.applicant.name, source_shift_id=swap.source_shift_id, source_duty_date=swap.source_shift.schedule_day.duty_date, target_person_id=swap.target_person_id, target_person_name=swap.target_person.name, target_shift_id=swap.target_shift_id, target_duty_date=swap.target_shift.schedule_day.duty_date if swap.target_shift else None, reason=swap.reason, status=swap.status, submitted_at=swap.submitted_at, effective_at=swap.effective_at)


@router.post("", response_model=ApiResponse[ShiftSwapResponse])
def create(payload: ShiftSwapCreateRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("swap:apply:create"))):
    swap = create_swap(db, payload, user, resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_response(get_swap(db, swap.id)))


@router.get("", response_model=ApiResponse[PageResponse[ShiftSwapResponse]])
def list_swaps(view: str = Query("related", pattern="^(initiated|pending|related)$"), paging: PageParams = Depends(get_page_params), db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("duty:swap:view_self"))):
    if user.person_id is None:
        raise ForbiddenError(message="当前账号未绑定人员")
    condition = ShiftSwap.applicant_person_id == user.person_id if view == "initiated" else ShiftSwap.target_person_id == user.person_id if view == "pending" else or_(ShiftSwap.applicant_person_id == user.person_id, ShiftSwap.target_person_id == user.person_id)
    stmt = select(ShiftSwap).where(condition).options(
        selectinload(ShiftSwap.applicant), selectinload(ShiftSwap.target_person),
        selectinload(ShiftSwap.source_shift).selectinload(ScheduleShift.schedule_day),
        selectinload(ShiftSwap.target_shift).selectinload(ScheduleShift.schedule_day),
    )
    rows = db.scalars(stmt.order_by(ShiftSwap.created_at.desc()).offset(paging.offset).limit(paging.page_size)).all()
    total = db.scalar(select(func.count()).select_from(ShiftSwap).where(condition)) or 0
    return ok(PageResponse.create(items=[_response(row) for row in rows], total=total, params=paging))


@router.get("/eligible-persons", response_model=ApiResponse[list[dict[str, object]]])
def eligible_persons(request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("swap:apply:create"))):
    """Return only same-room, enabled, account-bound duty operators for the form."""
    room_id = resolve_current_room_id(request, db, user)
    from app.models.person import Person
    rows = db.scalars(
        select(Person)
        .options(selectinload(Person.account))
        .where(
            Person.org_unit_id == room_id,
            Person.status == "enabled",
            Person.person_type == "duty_operator",
            Person.id != user.person_id,
        )
        .order_by(Person.name)
    ).all()
    return ok([{
        "id": person.id,
        "name": person.name,
        "eligible": bool(person.account and person.account.status == "enabled"),
        "disabled_reason": None if person.account and person.account.status == "enabled" else "未绑定启用账号，无法确认换班",
    } for person in rows])


@router.get("/eligible-shifts", response_model=ApiResponse[list[dict[str, object]]])
def eligible_shifts(person_id: int, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("swap:apply:create"))):
    room_id = resolve_current_room_id(request, db, user)
    rows = db.execute(
        select(ScheduleShift.id, ScheduleDay.duty_date, ShiftDef.name.label("shift_name"), ScheduleShift.start_at)
        .join(ScheduleDay).join(MonthlySchedule, ScheduleDay.schedule_id == MonthlySchedule.id)
        .join(ShiftDef, ShiftDef.id == ScheduleShift.shift_def_id)
        .join(ScheduleShiftPerson)
        .where(ScheduleShiftPerson.person_id == person_id, MonthlySchedule.org_unit_id == room_id, MonthlySchedule.status == "published")
        .order_by(ScheduleDay.duty_date)
    ).all()
    # The service remains the authority for published/locked/duplicate validation.
    return ok([{
        "id": row.id,
        "duty_date": row.duty_date.isoformat(),
        "shift_name": row.shift_name,
        "start_at": row.start_at.isoformat(),
    } for row in rows])


@router.post("/{swap_id}/target-confirm", response_model=ApiResponse[ShiftSwapResponse])
def confirm(swap_id: int, payload: ShiftSwapActionRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("swap:apply:confirm"))):
    swap = target_confirm(db, swap_id, user, approve=True, opinion=payload.opinion, room_id=resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_response(get_swap(db, swap.id)))


@router.post("/{swap_id}/target-reject", response_model=ApiResponse[ShiftSwapResponse])
def reject_target(swap_id: int, payload: ShiftSwapActionRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("swap:apply:confirm"))):
    swap = target_confirm(db, swap_id, user, approve=False, opinion=payload.opinion, room_id=resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_response(get_swap(db, swap.id)))


@router.post("/{swap_id}/withdraw", response_model=ApiResponse[ShiftSwapResponse])
def withdraw(swap_id: int, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("swap:apply:create"))):
    swap = withdraw_or_cancel(db, swap_id, user)
    db.commit()
    return ok(_response(get_swap(db, swap.id)))


@router.post("/{swap_id}/cancel", response_model=ApiResponse[ShiftSwapResponse])
def cancel(swap_id: int, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("swap:apply:create"))):
    swap = withdraw_or_cancel(db, swap_id, user, cancel=True)
    db.commit()
    return ok(_response(get_swap(db, swap.id)))
