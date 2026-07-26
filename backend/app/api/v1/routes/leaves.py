from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import RequirePermission, get_authenticated_user, get_db, get_page_params, resolve_current_room_id
from app.core.exceptions import ForbiddenError
from app.models.holiday import HolidayCalendar
from app.models.person import Person
from app.models.schedule import (
    CoverAssignment,
    LeaveRequest,
    MonthlySchedule,
    ScheduleDay,
    ScheduleShift,
    ScheduleShiftPerson,
)
from app.models.shift import ShiftDef
from app.models.user import SysUser
from app.schemas.leave import (
    CoverActionRequest,
    CoverArrangeRequest,
    CoverCancelRequest,
    CoverResponse,
    LeaveCreateRequest,
    LeaveResponse,
)
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.services.leave import arrange_cover, cancel_cover, confirm_cover, create_leave, get_cover, withdraw_leave

router = APIRouter(prefix="/leaves", tags=["leaves"])
covers_router = APIRouter(prefix="/cover-assignments", tags=["cover-assignments"])


def _leave_response(item: LeaveRequest, cover: CoverAssignment | None = None) -> LeaveResponse:
    return LeaveResponse(id=item.id, biz_no=item.biz_no, applicant_person_id=item.applicant_person_id, applicant_name=item.applicant.name, schedule_shift_id=item.schedule_shift_id, duty_date=item.schedule_shift.schedule_day.duty_date, leave_type=item.leave_type, reason=item.reason, status=item.status, cover_status=cover.status if cover else None, cover_assignment_id=cover.id if cover else None, cover_person_id=cover.cover_person_id if cover else None, cover_person_name=cover.cover_person.name if cover and cover.cover_person else None, submitted_at=item.submitted_at)


def _cover_response(item: CoverAssignment) -> CoverResponse:
    return CoverResponse(id=item.id, biz_no=item.biz_no, leave_request_id=item.leave_request_id, cover_person_id=item.cover_person_id, cover_person_name=item.cover_person.name if item.cover_person else None, status=item.status, remark=item.remark, duty_date=item.leave_request.schedule_shift.schedule_day.duty_date, applicant_name=item.leave_request.applicant.name)


@router.post("", response_model=ApiResponse[LeaveResponse])
def create(payload: LeaveCreateRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user)) -> ApiResponse[LeaveResponse]:
    leave = create_leave(db, payload, user, resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_leave_response(_get_leave(db, leave.id)))


def _get_leave(db: Session, leave_id: int) -> LeaveRequest:
    return db.scalar(select(LeaveRequest).where(LeaveRequest.id == leave_id).options(selectinload(LeaveRequest.applicant), selectinload(LeaveRequest.schedule_shift).selectinload(ScheduleShift.schedule_day)))  # type: ignore[return-value]


@router.get("", response_model=ApiResponse[PageResponse[LeaveResponse]])
def list_leaves(request: Request, view: str = Query("mine", pattern="^(mine|room)$"), month: str | None = None, paging: PageParams = Depends(get_page_params), db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user)) -> ApiResponse[PageResponse[LeaveResponse]]:
    room_id = resolve_current_room_id(request, db, user)
    if view == "room":
        from app.services.auth import check_user_permission
        if not check_user_permission(db, user, "leave:record:view"):
            raise ForbiddenError(message="缺少权限: leave:record:view")
        filters = [ScheduleDay.schedule.has(org_unit_id=room_id)]
    else:
        if user.person_id is None:
            raise ForbiddenError(message="当前账号未绑定人员")
        filters = [LeaveRequest.applicant_person_id == user.person_id]
    if month:
        filters.extend([ScheduleDay.duty_date >= date.fromisoformat(f"{month}-01"), ScheduleDay.duty_date < date.fromisoformat(f"{int(month[:4]) + (month[5:7] == '12'):04d}-{(int(month[5:7]) % 12) + 1:02d}-01")])
    stmt = select(LeaveRequest).join(LeaveRequest.schedule_shift).join(ScheduleShift.schedule_day).where(*filters).options(selectinload(LeaveRequest.applicant), selectinload(LeaveRequest.schedule_shift).selectinload(ScheduleShift.schedule_day))
    total = db.scalar(select(func.count()).select_from(LeaveRequest).join(LeaveRequest.schedule_shift).join(ScheduleShift.schedule_day).where(*filters)) or 0
    rows = db.scalars(stmt.order_by(LeaveRequest.created_at.desc()).offset(paging.offset).limit(paging.page_size)).all()
    covers = {row.leave_request_id: row for row in db.scalars(select(CoverAssignment).where(CoverAssignment.leave_request_id.in_([row.id for row in rows])).options(selectinload(CoverAssignment.cover_person))).all()}
    return ok(PageResponse.create(items=[_leave_response(row, covers.get(row.id)) for row in rows], total=total, params=paging))


@router.get("/eligible-shifts", response_model=ApiResponse[list[dict[str, object]]])
def eligible_leave_shifts(request: Request, db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user)) -> ApiResponse[list[dict[str, object]]]:
    """Future, published own shifts which are eligible for an ordinary leave request."""
    if user.person_id is None:
        raise ForbiddenError(message="当前账号未绑定人员")
    room_id = resolve_current_room_id(request, db, user)
    rows = db.execute(
        select(ScheduleShift.id, ScheduleDay.duty_date, ShiftDef.name.label("shift_name"), ScheduleShift.start_at)
        .join(ScheduleDay, ScheduleDay.id == ScheduleShift.schedule_day_id)
        .join(MonthlySchedule, MonthlySchedule.id == ScheduleDay.schedule_id)
        .join(ShiftDef, ShiftDef.id == ScheduleShift.shift_def_id)
        .join(ScheduleShiftPerson, ScheduleShiftPerson.schedule_shift_id == ScheduleShift.id)
        .where(
            ScheduleShiftPerson.person_id == user.person_id,
            MonthlySchedule.org_unit_id == room_id,
            MonthlySchedule.status == "published",
            ScheduleDay.duty_date >= date.today(),
            ScheduleDay.is_legal_holiday.is_(False),
            ~exists(select(HolidayCalendar.id).where(
                HolidayCalendar.holiday_date == ScheduleDay.duty_date,
                HolidayCalendar.is_legal.is_(True),
                HolidayCalendar.status == "enabled",
            )),
        )
        .order_by(ScheduleDay.duty_date, ScheduleShift.start_at)
    ).all()
    return ok([{"id": row.id, "duty_date": row.duty_date.isoformat(), "shift_name": row.shift_name, "start_at": row.start_at.isoformat()} for row in rows])


@router.post("/{leave_id}/withdraw", response_model=ApiResponse[LeaveResponse])
def withdraw(leave_id: int, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user)) -> ApiResponse[LeaveResponse]:
    leave = withdraw_leave(db, leave_id, user, resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_leave_response(_get_leave(db, leave.id)))


@covers_router.get("/mine", response_model=ApiResponse[PageResponse[CoverResponse]])
def my_covers(request: Request, paging: PageParams = Depends(get_page_params), db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user)) -> ApiResponse[PageResponse[CoverResponse]]:
    if user.person_id is None:
        raise ForbiddenError(message="当前账号未绑定人员")
    room_id = resolve_current_room_id(request, db, user)
    stmt = select(CoverAssignment).join(CoverAssignment.leave_request).join(LeaveRequest.schedule_shift).join(ScheduleShift.schedule_day).where(CoverAssignment.cover_person_id == user.person_id, ScheduleDay.schedule.has(org_unit_id=room_id)).options(selectinload(CoverAssignment.cover_person), selectinload(CoverAssignment.leave_request).selectinload(LeaveRequest.applicant), selectinload(CoverAssignment.leave_request).selectinload(LeaveRequest.schedule_shift).selectinload(ScheduleShift.schedule_day))
    total = db.scalar(
        select(func.count())
        .select_from(CoverAssignment)
        .join(CoverAssignment.leave_request)
        .join(LeaveRequest.schedule_shift)
        .join(ScheduleShift.schedule_day)
        .where(CoverAssignment.cover_person_id == user.person_id, ScheduleDay.schedule.has(org_unit_id=room_id))
    ) or 0
    return ok(PageResponse.create(items=[_cover_response(row) for row in db.scalars(stmt.order_by(CoverAssignment.created_at.desc()).offset(paging.offset).limit(paging.page_size)).all()], total=total, params=paging))


@covers_router.get("/pending", response_model=ApiResponse[PageResponse[CoverResponse]])
def pending_covers(request: Request, paging: PageParams = Depends(get_page_params), db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("cover:assignment:view"))) -> ApiResponse[PageResponse[CoverResponse]]:
    room_id = resolve_current_room_id(request, db, user)
    stmt = select(CoverAssignment).join(CoverAssignment.leave_request).join(LeaveRequest.schedule_shift).join(ScheduleShift.schedule_day).where(CoverAssignment.status.in_(("pending_arrangement", "rearrange")), ScheduleDay.schedule.has(org_unit_id=room_id)).options(selectinload(CoverAssignment.cover_person), selectinload(CoverAssignment.leave_request).selectinload(LeaveRequest.applicant), selectinload(CoverAssignment.leave_request).selectinload(LeaveRequest.schedule_shift).selectinload(ScheduleShift.schedule_day))
    rows = db.scalars(stmt.offset(paging.offset).limit(paging.page_size)).all()
    return ok(PageResponse.create(items=[_cover_response(row) for row in rows], total=len(rows), params=paging))


@covers_router.get("/eligible-persons", response_model=ApiResponse[list[dict[str, object]]])
def eligible_cover_persons(request: Request, cover_id: int | None = None, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("cover:assignment:view"))) -> ApiResponse[list[dict[str, object]]]:
    room_id = resolve_current_room_id(request, db, user)
    duty_date = None
    if cover_id is not None:
        cover = get_cover(db, cover_id)
        if cover.leave_request.schedule_shift.schedule_day.schedule.org_unit_id != room_id:
            raise ForbiddenError(message="仅能管理当前机房顶班")
        duty_date = cover.leave_request.schedule_shift.schedule_day.duty_date
    rows = db.scalars(select(Person).where(Person.org_unit_id == room_id, Person.status == "enabled", Person.person_type.in_(("maintenance", "room_director", "deputy_director"))).options(selectinload(Person.account)).order_by(Person.name)).all()
    person_ids = [row.id for row in rows]
    duty_summaries: dict[int, list[str]] = {person_id: [] for person_id in person_ids}
    cover_summaries: dict[int, list[str]] = {person_id: [] for person_id in person_ids}
    if duty_date and person_ids:
        duty_rows = db.execute(
            select(ScheduleShiftPerson.person_id, ScheduleShift.shift_def_id)
            .join(ScheduleShift, ScheduleShift.id == ScheduleShiftPerson.schedule_shift_id)
            .join(ScheduleDay, ScheduleDay.id == ScheduleShift.schedule_day_id)
            .where(ScheduleShiftPerson.person_id.in_(person_ids), ScheduleDay.duty_date == duty_date)
        ).all()
        for person_id, shift_def_id in duty_rows:
            duty_summaries[person_id].append(f"班次#{shift_def_id}")
        cover_rows = db.execute(
            select(CoverAssignment.cover_person_id, CoverAssignment.biz_no)
            .join(LeaveRequest, LeaveRequest.id == CoverAssignment.leave_request_id)
            .join(ScheduleShift, ScheduleShift.id == LeaveRequest.schedule_shift_id)
            .join(ScheduleDay, ScheduleDay.id == ScheduleShift.schedule_day_id)
            .where(CoverAssignment.cover_person_id.in_(person_ids), CoverAssignment.status.in_(("wait_cover_confirm", "effective")), ScheduleDay.duty_date == duty_date)
        ).all()
        for person_id, biz_no in cover_rows:
            if person_id is not None:
                cover_summaries[person_id].append(str(biz_no))
    return ok([{"id": row.id, "name": row.name, "person_type": row.person_type, "eligible": bool(row.account and row.account.status == "enabled"), "disabled_reason": None if row.account and row.account.status == "enabled" else "未绑定启用账号", "duty_summary": "、".join(duty_summaries[row.id]) or "当日无排班", "cover_summary": "、".join(cover_summaries[row.id]) or "当日无顶班"} for row in rows])


@covers_router.post("/{cover_id}/arrange", response_model=ApiResponse[CoverResponse])
def arrange(cover_id: int, payload: CoverArrangeRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("cover:assignment:view"))) -> ApiResponse[CoverResponse]:
    cover = arrange_cover(db, cover_id, payload.cover_person_id, payload.remark, user, resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_cover_response(get_cover(db, cover.id)))


@covers_router.post("/{cover_id}/cancel", response_model=ApiResponse[CoverResponse])
def cancel(cover_id: int, payload: CoverCancelRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("cover:assignment:view"))) -> ApiResponse[CoverResponse]:
    cover = cancel_cover(db, cover_id, payload.reason, user, resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_cover_response(get_cover(db, cover.id)))


@covers_router.post("/{cover_id}/confirm", response_model=ApiResponse[CoverResponse])
def confirm(cover_id: int, payload: CoverActionRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user)) -> ApiResponse[CoverResponse]:
    cover = confirm_cover(db, cover_id, user, approve=True, opinion=payload.opinion, room_id=resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_cover_response(get_cover(db, cover.id)))


@covers_router.post("/{cover_id}/reject", response_model=ApiResponse[CoverResponse])
def reject(cover_id: int, payload: CoverActionRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user)) -> ApiResponse[CoverResponse]:
    cover = confirm_cover(db, cover_id, user, approve=False, opinion=payload.opinion, room_id=resolve_current_room_id(request, db, user))
    db.commit()
    return ok(_cover_response(get_cover(db, cover.id)))
