from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db, get_page_params
from app.core.exceptions import NotFoundError
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.user import SysUser
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.schemas.schedule import (
    ScheduleDayResponse,
    ScheduleResponse,
    ScheduleShiftPersonResponse,
    ScheduleShiftResponse,
)
from app.services.auth import resolve_scoped_org_unit_ids
from app.services.schedule import get_schedule, get_schedule_days, list_schedules

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _build_schedule_response(schedule: MonthlySchedule) -> ScheduleResponse:
    org = schedule.org_unit
    rule = schedule.rule
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
    return ScheduleResponse(
        id=schedule.id,
        org_unit_id=schedule.org_unit_id,
        org_unit_code=org.code if org else "",
        org_unit_name=org.name if org else "",
        year_month=schedule.year_month,
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


def _build_day_response(day: ScheduleDay) -> ScheduleDayResponse:
    return ScheduleDayResponse(
        id=day.id,
        duty_date=day.duty_date,
        weekday=day.weekday,
        is_legal_holiday=day.is_legal_holiday,
        holiday_name=day.holiday_name,
        shifts=[_build_shift_response(sh) for sh in (day.shifts or [])],
    )


@router.get("", response_model=ApiResponse[PageResponse[ScheduleResponse]])
def list_schedules_endpoint(
    paging: PageParams = Depends(get_page_params),
    org_unit_id: int | None = None,
    year_month: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[PageResponse[ScheduleResponse]]:
    scoped_ids = resolve_scoped_org_unit_ids(db, user)
    schedules, total = list_schedules(
        db,
        org_unit_ids=scoped_ids,
        org_unit_id=org_unit_id,
        year_month=year_month,
        status=status,
        offset=paging.offset,
        limit=paging.page_size,
    )
    items = [_build_schedule_response(s) for s in schedules]
    return ok(PageResponse.create(items=items, total=total, params=paging))


@router.get("/{id}", response_model=ApiResponse[ScheduleResponse])
def get_schedule_endpoint(
    id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[ScheduleResponse]:
    schedule = get_schedule(db, id)
    if schedule is None:
        raise NotFoundError(message="排班记录不存在")
    return ok(_build_schedule_response(schedule))


@router.get("/{id}/days", response_model=ApiResponse[list[ScheduleDayResponse]])
def get_schedule_days_endpoint(
    id: int,
    db: Session = Depends(get_db),
    _perm: None = Depends(RequirePermission("schedule:monthly:view")),
) -> ApiResponse[list[ScheduleDayResponse]]:
    schedule = get_schedule(db, id)
    if schedule is None:
        raise NotFoundError(message="排班记录不存在")
    days = get_schedule_days(db, id)
    return ok([_build_day_response(d) for d in days])
