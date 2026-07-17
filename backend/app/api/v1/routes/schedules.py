from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db, get_page_params, resolve_current_room_id
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftRule, ShiftRuleVersion
from app.models.user import SysUser
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.schemas.schedule import (
    ScheduleDayResponse,
    ScheduleResponse,
    ScheduleShiftPersonResponse,
    ScheduleShiftResponse,
)
from app.services.schedule import (
    generate_schedule_from_rule,
    get_legal_holidays,
    get_schedule_counts,
    get_schedule_days,
    get_schedule_days_by_range,
    list_schedules,
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


def _get_scoped_schedule(db: Session, schedule_id: int, room_id: int) -> MonthlySchedule:
    schedule = db.scalar(select(MonthlySchedule).where(MonthlySchedule.id == schedule_id))
    if schedule is None:
        raise NotFoundError(message="排班记录不存在")

    if schedule.org_unit_id != room_id:
        raise NotFoundError(message="排班记录不存在")
    return schedule


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
    schedules, total = list_schedules(
        db,
        org_unit_id=room_id,
        status=status,
        offset=paging.offset,
        limit=paging.page_size,
    )
    counts = get_schedule_counts(db, [schedule.id for schedule in schedules])
    items = [_build_schedule_response(s, counts.get(s.id)) for s in schedules]
    return ok(PageResponse.create(items=items, total=total, params=paging))


@router.get("/{id}", response_model=ApiResponse[ScheduleResponse])
def get_schedule_endpoint(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[ScheduleResponse]:
    schedule = _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
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
    _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
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
    _get_scoped_schedule(db, id, resolve_current_room_id(request, db, user))
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
