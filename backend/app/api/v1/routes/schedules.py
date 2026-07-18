from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import RequirePermission, get_db, get_page_params, resolve_current_room_id
from app.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError, StateConflictError
from app.models.schedule import DutyChangeLedger, MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson, ShiftSwap
from app.models.person import Person
from app.models.shift import ShiftRule, ShiftRuleVersion
from app.models.user import SysUser
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.services.auth import check_user_permission
from app.schemas.schedule import (
    ScheduleDayResponse,
    DutyChangeLedgerResponse,
    HistoricalCorrectionRequest,
    ScheduleResponse,
    SchedulePersonOptionResponse,
    ScheduleShiftUpdateRequest,
    ScheduleShiftPersonResponse,
    ScheduleShiftResponse,
)
from app.services.schedule import (
    generate_schedule_from_rule,
    get_legal_holidays,
    get_schedule_counts,
    get_schedule_days,
    get_schedule_days_by_range,
    apply_historical_correction,
    list_schedules,
    update_schedule_shift_persons,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _build_schedule_response(
    schedule: MonthlySchedule,
    counts: tuple[int, int, int, date | None] | None = None,
) -> ScheduleResponse:
    org = schedule.org_unit
    rule = schedule.rule
    if counts is not None:
        day_count, shift_count, person_count, coverage_through = counts
    else:
        days = schedule.days
        day_count = len(days) if days else 0
        shift_count = 0
        person_count = 0
        if days:
            for d in days:
                shifts = d.shifts if d.shifts else []
                shift_count += len(shifts)
                for sh in shifts:
                    persons = sh.persons if sh.persons else []
                    person_count += len(persons)
        coverage_through = max((day.duty_date for day in days), default=None)
    return ScheduleResponse(
        id=schedule.id,
        org_unit_id=schedule.org_unit_id,
        org_unit_code=org.code if org else "",
        org_unit_name=org.name if org else "",
        rule_id=schedule.rule_id,
        rule_code=rule.code if rule else "",
        rule_name=rule.name if rule else "",
        status=schedule.status,
        generated_at=schedule.generated_at,
        published_at=schedule.published_at,
        locked_at=schedule.locked_at,
        remark=schedule.remark,
        day_count=day_count,
        shift_count=shift_count,
        person_count=person_count,
        coverage_through=coverage_through,
    )


def _build_shift_person_response(sp: ScheduleShiftPerson) -> ScheduleShiftPersonResponse:
    p = sp.person
    return ScheduleShiftPersonResponse(
        id=sp.id,
        person_id=sp.person_id,
        person_code=p.code if p else "",
        person_name=p.name if p else "",
        position_no=sp.position_no,
        source_type=sp.source_type,
        remark=sp.remark,
    )


def _build_shift_response(
    shift: ScheduleShift, pending_change_summary: str | None = None, effective_change_summary: str | None = None,
) -> ScheduleShiftResponse:
    sd = shift.shift_def
    return ScheduleShiftResponse(
        id=shift.id,
        shift_def_id=shift.shift_def_id,
        shift_def_code=sd.code if sd else "",
        shift_def_name=sd.name if sd else "",
        start_at=shift.start_at,
        end_at=shift.end_at,
        status=shift.status,
        change_types=sorted({sp.source_type for sp in (shift.persons or []) if sp.source_type != "auto"}),
        effective_change_summary=effective_change_summary,
        pending_change_summary=pending_change_summary,
        persons=[_build_shift_person_response(sp) for sp in (shift.persons or [])],
    )


def _build_day_response(
    day: ScheduleDay, holidays: dict[date, str], pending_summaries: dict[int, str] | None = None,
    effective_summaries: dict[int, str] | None = None,
) -> ScheduleDayResponse:
    return ScheduleDayResponse(
        id=day.id,
        duty_date=day.duty_date,
        weekday=day.weekday,
        is_legal_holiday=day.duty_date in holidays,
        holiday_name=holidays.get(day.duty_date),
        shifts=[_build_shift_response(sh, (pending_summaries or {}).get(sh.id), (effective_summaries or {}).get(sh.id)) for sh in (day.shifts or [])],
    )


def _get_pending_swap_summaries(db: Session, days: list[ScheduleDay]) -> dict[int, str]:
    shift_ids = [shift.id for day in days for shift in day.shifts]
    if not shift_ids:
        return {}
    swaps = list(db.scalars(
        select(ShiftSwap)
        .where(ShiftSwap.status.in_(("wait_target_confirm", "wait_director_approval")))
        .where((ShiftSwap.source_shift_id.in_(shift_ids)) | (ShiftSwap.target_shift_id.in_(shift_ids)))
        .options(selectinload(ShiftSwap.applicant), selectinload(ShiftSwap.target_person))
    ).all())
    summaries: dict[int, str] = {}
    for swap in swaps:
        status = "待对方确认" if swap.status == "wait_target_confirm" else "待主任审批"
        summaries[swap.source_shift_id] = f"拟变更：{swap.applicant.name} → {swap.target_person.name}，{status}"
        if swap.target_shift_id:
            summaries[swap.target_shift_id] = f"拟变更：{swap.target_person.name} → {swap.applicant.name}，{status}"
    return summaries


def _get_effective_change_summaries(db: Session, days: list[ScheduleDay]) -> dict[int, str]:
    shift_ids = [shift.id for day in days for shift in day.shifts]
    if not shift_ids:
        return {}
    rows = list(db.scalars(
        select(DutyChangeLedger)
        .where(DutyChangeLedger.schedule_shift_id.in_(shift_ids))
        .options(selectinload(DutyChangeLedger.before_person), selectinload(DutyChangeLedger.after_person))
        .order_by(DutyChangeLedger.schedule_shift_id, DutyChangeLedger.created_at.desc())
    ).all())
    labels = {"swap": "换班", "swap_cancel": "换班作废", "leave_cover": "请假顶班", "historical_correction": "历史修正", "manual": "人工调整"}
    summaries: dict[int, str] = {}
    for row in rows:
        summaries.setdefault(
            row.schedule_shift_id,
            f"已生效{labels.get(row.change_type, row.change_type)}：{row.before_person.name} → {row.after_person.name}",
        )
    return summaries


def _build_ledger_response(row: DutyChangeLedger, creator_names: dict[int, str]) -> DutyChangeLedgerResponse:
    shift = row.schedule_shift
    return DutyChangeLedgerResponse(
        id=row.id, duty_date=shift.schedule_day.duty_date, shift_def_id=shift.shift_def_id,
        shift_def_name=shift.shift_def.name if shift.shift_def else "",
        start_at=shift.start_at, end_at=shift.end_at,
        original_person_name=row.original_person.name, before_person_name=row.before_person.name,
        after_person_name=row.after_person.name, change_type=row.change_type,
        source_biz_no=row.source_biz_no, reason=row.reason, created_at=row.created_at, created_by=row.created_by,
        created_by_name=creator_names.get(row.created_by) if row.created_by else None,
    )


def _get_scoped_schedule(db: Session, schedule_id: int, room_id: int) -> MonthlySchedule:
    schedule = db.scalar(select(MonthlySchedule).where(MonthlySchedule.id == schedule_id))
    if schedule is None:
        raise NotFoundError(message="排班记录不存在")

    if schedule.org_unit_id != room_id:
        raise NotFoundError(message="排班记录不存在")
    return schedule


def _ensure_schedule_visible(db: Session, schedule: MonthlySchedule, user: SysUser) -> None:
    if schedule.status != "published" and not check_user_permission(db, user, "schedule:monthly:generate"):
        raise NotFoundError(message="排班记录不存在")


@router.get("", response_model=ApiResponse[PageResponse[ScheduleResponse]])
def list_schedules_endpoint(
    request: Request,
    paging: PageParams = Depends(get_page_params),
    org_unit_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[PageResponse[ScheduleResponse]]:
    room_id = resolve_current_room_id(request, db, user)
    visible_status = status
    if not check_user_permission(db, user, "schedule:monthly:generate"):
        visible_status = "published"
    schedules, total = list_schedules(
        db,
        org_unit_id=room_id,
        status=visible_status,
        offset=paging.offset,
        limit=paging.page_size,
    )
    counts = get_schedule_counts(db, [schedule.id for schedule in schedules])
    items = [_build_schedule_response(s, counts.get(s.id)) for s in schedules]
    return ok(PageResponse.create(items=items, total=total, params=paging))


@router.get("/change-ledger", response_model=ApiResponse[PageResponse[DutyChangeLedgerResponse]])
def list_change_ledger_endpoint(
    request: Request, paging: PageParams = Depends(get_page_params),
    from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"),
    person_id: int | None = None, shift_def_id: int | None = None, change_type: str | None = None,
    db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("duty:actual:view")),
) -> ApiResponse[PageResponse[DutyChangeLedgerResponse]]:
    if from_date and to_date and from_date > to_date:
        raise BusinessRuleError(message="起始日期不能晚于结束日期")
    room_id = resolve_current_room_id(request, db, user)
    stmt = select(DutyChangeLedger).join(ScheduleShift).join(ScheduleDay).join(MonthlySchedule).where(MonthlySchedule.org_unit_id == room_id)
    if from_date: stmt = stmt.where(ScheduleDay.duty_date >= from_date)
    if to_date: stmt = stmt.where(ScheduleDay.duty_date <= to_date)
    if person_id: stmt = stmt.where((DutyChangeLedger.original_person_id == person_id) | (DutyChangeLedger.before_person_id == person_id) | (DutyChangeLedger.after_person_id == person_id))
    if shift_def_id: stmt = stmt.where(ScheduleShift.shift_def_id == shift_def_id)
    if change_type: stmt = stmt.where(DutyChangeLedger.change_type == change_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.options(
        selectinload(DutyChangeLedger.original_person), selectinload(DutyChangeLedger.before_person), selectinload(DutyChangeLedger.after_person),
        selectinload(DutyChangeLedger.schedule_shift).selectinload(ScheduleShift.shift_def),
        selectinload(DutyChangeLedger.schedule_shift).selectinload(ScheduleShift.schedule_day),
    ).order_by(ScheduleDay.duty_date.desc(), DutyChangeLedger.created_at.desc()).offset(paging.offset).limit(paging.page_size)).all())
    creator_ids = {row.created_by for row in rows if row.created_by}
    creator_names = {
        user.id: user.display_name
        for user in db.scalars(select(SysUser).where(SysUser.id.in_(creator_ids))).all()
    } if creator_ids else {}
    return ok(PageResponse.create(items=[_build_ledger_response(row, creator_names) for row in rows], total=total, params=paging))


@router.get("/{id}", response_model=ApiResponse[ScheduleResponse])
def get_schedule_endpoint(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[ScheduleResponse]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
    _ensure_schedule_visible(db, schedule, user)
    return ok(_build_schedule_response(schedule, get_schedule_counts(db, [schedule.id]).get(schedule.id)))


@router.get("/{id}/days", response_model=ApiResponse[list[ScheduleDayResponse]])
def get_schedule_days_endpoint(
    id: int,
    request: Request,
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[list[ScheduleDayResponse]]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
    _ensure_schedule_visible(db, schedule, user)
    if (year is None) != (month is None):
        raise BusinessRuleError(message="year 和 month 必须同时传入")
    if year is not None and not 1 <= year <= 9999:
        raise BusinessRuleError(message="year 必须在 1 到 9999 之间")
    if month is not None and not 1 <= month <= 12:
        raise BusinessRuleError(message="month 必须在 1 到 12 之间")
    days = get_schedule_days(db, id, year=year, month=month)
    holidays = get_legal_holidays(db, [day.duty_date for day in days])
    pending_summaries = _get_pending_swap_summaries(db, days)
    effective_summaries = _get_effective_change_summaries(db, days)
    return ok([_build_day_response(day, holidays, pending_summaries, effective_summaries) for day in days])


@router.get("/{id}/days/range", response_model=ApiResponse[list[ScheduleDayResponse]])
def get_schedule_days_range_endpoint(
    id: int,
    request: Request,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[list[ScheduleDayResponse]]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
    _ensure_schedule_visible(db, schedule, user)
    if from_date > to_date:
        raise BusinessRuleError(message="起始日期不能晚于结束日期")
    if (to_date - from_date).days > 365:
        raise BusinessRuleError(message="日期范围不能超过 366 天")
    days = get_schedule_days_by_range(db, id, from_date=from_date, to_date=to_date)
    holidays = get_legal_holidays(db, [day.duty_date for day in days])
    pending_summaries = _get_pending_swap_summaries(db, days)
    effective_summaries = _get_effective_change_summaries(db, days)
    return ok([_build_day_response(day, holidays, pending_summaries, effective_summaries) for day in days])


@router.post("/{id}/generate", response_model=ApiResponse[ScheduleResponse])
def generate_schedule_endpoint(
    id: int,
    request: Request,
    through: date | None = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:generate")),
) -> ApiResponse[ScheduleResponse]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))

    rule = db.get(ShiftRule, schedule.rule_id)
    if rule is None or rule.status != "published":
        raise BusinessRuleError(message="关联的排班规则未发布")

    latest_version = db.scalars(
        select(ShiftRuleVersion)
        .where(ShiftRuleVersion.rule_id == rule.id)
        .where(ShiftRuleVersion.status == "published")
        .order_by(ShiftRuleVersion.version_no.desc())
        .limit(1)
    ).first()
    if latest_version is None:
        raise BusinessRuleError(message="规则没有已发布的版本")

    generate_schedule_from_rule(db, rule, latest_version, through_date=through)
    db.commit()
    db.refresh(schedule)
    return ok(_build_schedule_response(schedule, get_schedule_counts(db, [schedule.id]).get(schedule.id)))

@router.put("/{id}/shifts/{shift_id}/persons", response_model=ApiResponse[ScheduleShiftResponse])
def update_schedule_shift_endpoint(
    id: int, shift_id: int, payload: ScheduleShiftUpdateRequest, request: Request,
    db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("schedule:monthly:generate")),
) -> ApiResponse[ScheduleShiftResponse]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
    shift = db.scalar(select(ScheduleShift).join(ScheduleDay).where(
        ScheduleShift.id == shift_id, ScheduleDay.schedule_id == schedule.id,
    ))
    if shift is None:
        raise NotFoundError(message="排班班次不存在")
    if "system_admin" in {role.code for role in user.roles} and (
        user.person_id is None or user.person_id not in {person.person_id for person in shift.persons}
    ):
        raise ForbiddenError(message="系统管理员仅可编辑本人班次")
    duty_date = db.scalar(select(ScheduleDay.duty_date).where(ScheduleDay.id == shift.schedule_day_id))
    if duty_date is not None and duty_date < date.today():
        raise BusinessRuleError(message="历史班次仅可通过历史修正调整")
    update_schedule_shift_persons(db, schedule, shift, payload.person_ids, payload.remark, actor_id=user.id)
    db.commit()
    db.refresh(shift)
    return ok(_build_shift_response(shift))


@router.post("/{id}/shifts/{shift_id}/history-corrections", response_model=ApiResponse[ScheduleShiftResponse])
def historical_correction_endpoint(
    id: int, shift_id: int, payload: HistoricalCorrectionRequest, request: Request,
    db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("schedule:monthly:generate")),
) -> ApiResponse[ScheduleShiftResponse]:
    if not {role.code for role in user.roles} & {"room_director", "deputy_director"}:
        raise ForbiddenError(message="仅机房主任或副主任可执行历史修正")
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
    shift = db.scalar(select(ScheduleShift).join(ScheduleDay).where(ScheduleShift.id == shift_id, ScheduleDay.schedule_id == schedule.id).options(selectinload(ScheduleShift.schedule_day)))
    if shift is None:
        raise NotFoundError(message="排班班次不存在")
    apply_historical_correction(db, schedule, shift, payload.person_ids, payload.reason, user.id)
    db.commit()
    db.refresh(shift)
    return ok(_build_shift_response(shift))


@router.get("/{id}/eligible-persons", response_model=ApiResponse[list[SchedulePersonOptionResponse]])
def list_schedule_eligible_persons_endpoint(
    id: int, request: Request, db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:generate")),
) -> ApiResponse[list[SchedulePersonOptionResponse]]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
    persons = list(db.scalars(select(Person).where(
        Person.org_unit_id == schedule.org_unit_id,
        Person.status == "enabled",
        Person.participate_schedule.is_(True),
        Person.person_type == "duty_operator",
    ).order_by(Person.code)).all())
    return ok([SchedulePersonOptionResponse(id=person.id, code=person.code, name=person.name) for person in persons])


@router.post("/{id}/publish", response_model=ApiResponse[ScheduleResponse])
def publish_schedule_endpoint(
    id: int, request: Request, db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:generate")),
) -> ApiResponse[ScheduleResponse]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
    if schedule.status == "locked":
        raise StateConflictError(message="已锁定排班不能发布")
    schedule.status = "published"
    from datetime import datetime, UTC
    schedule.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(schedule)
    return ok(_build_schedule_response(schedule, get_schedule_counts(db, [schedule.id]).get(schedule.id)))
