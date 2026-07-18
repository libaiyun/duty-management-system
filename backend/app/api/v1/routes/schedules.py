from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db, get_page_params, resolve_current_room_id
from app.core.exceptions import BusinessRuleError, NotFoundError, StateConflictError
from app.models.schedule import ActualDuty, MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.person import Person
from app.models.shift import ShiftRule, ShiftRuleVersion
from app.models.user import SysUser
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.services.auth import check_user_permission
from app.schemas.schedule import (
    ScheduleDayResponse,
    ActualDutyResponse,
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
    list_actual_duties,
    list_schedules,
    refresh_actual_duties,
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


def _build_shift_response(shift: ScheduleShift) -> ScheduleShiftResponse:
    sd = shift.shift_def
    return ScheduleShiftResponse(
        id=shift.id,
        shift_def_id=shift.shift_def_id,
        shift_def_code=sd.code if sd else "",
        shift_def_name=sd.name if sd else "",
        start_at=shift.start_at,
        end_at=shift.end_at,
        status=shift.status,
        persons=[_build_shift_person_response(sp) for sp in (shift.persons or [])],
    )


def _build_day_response(day: ScheduleDay, holidays: dict[date, str]) -> ScheduleDayResponse:
    return ScheduleDayResponse(
        id=day.id,
        duty_date=day.duty_date,
        weekday=day.weekday,
        is_legal_holiday=day.duty_date in holidays,
        holiday_name=holidays.get(day.duty_date),
        shifts=[_build_shift_response(sh) for sh in (day.shifts or [])],
    )


def _build_actual_duty_response(row: ActualDuty) -> ActualDutyResponse:
    return ActualDutyResponse(
        id=row.id, duty_date=row.duty_date, shift_def_id=row.shift_def_id,
        shift_def_name=row.shift_def.name if row.shift_def else "",
        original_person_id=row.original_person_id,
        original_person_name=row.original_person.name if row.original_person else "",
        actual_person_id=row.actual_person_id,
        actual_person_name=row.actual_person.name if row.actual_person else "",
        source_type=row.source_type, schedule_version=row.schedule_version,
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


@router.get("/actual-duties", response_model=ApiResponse[PageResponse[ActualDutyResponse]])
def list_actual_duties_endpoint(
    request: Request, paging: PageParams = Depends(get_page_params),
    from_date: date | None = Query(None, alias="from"), to_date: date | None = Query(None, alias="to"),
    person_id: int | None = None, shift_def_id: int | None = None, source_type: str | None = None,
    db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("duty:actual:view")),
) -> ApiResponse[PageResponse[ActualDutyResponse]]:
    if from_date and to_date and from_date > to_date:
        raise BusinessRuleError(message="起始日期不能晚于结束日期")
    rows, total = list_actual_duties(
        db, org_unit_id=resolve_current_room_id(request, db, user), from_date=from_date, to_date=to_date,
        person_id=person_id, shift_def_id=shift_def_id, source_type=source_type, offset=paging.offset, limit=paging.page_size,
    )
    return ok(PageResponse.create(items=[_build_actual_duty_response(row) for row in rows], total=total, params=paging))


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
    return ok([_build_day_response(day, holidays) for day in days])


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
    return ok([_build_day_response(day, holidays) for day in days])


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
    update_schedule_shift_persons(db, schedule, shift, payload.person_ids, payload.remark)
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
    refresh_actual_duties(db, schedule)
    db.commit()
    db.refresh(schedule)
    return ok(_build_schedule_response(schedule, get_schedule_counts(db, [schedule.id]).get(schedule.id)))
