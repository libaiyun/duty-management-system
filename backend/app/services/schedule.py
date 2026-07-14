from datetime import date, datetime, timedelta

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.holiday import HolidayCalendar
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleItem, ShiftRuleVersion


def list_schedules(
    db: Session,
    *,
    org_unit_ids: set[int] | None = None,
    org_unit_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[MonthlySchedule], int]:
    base_stmt = select(MonthlySchedule)

    if org_unit_ids is not None:
        if not org_unit_ids:
            return [], 0
        base_stmt = base_stmt.where(MonthlySchedule.org_unit_id.in_(org_unit_ids))

    if org_unit_id is not None:
        if org_unit_ids is not None and org_unit_id not in org_unit_ids:
            return [], 0
        base_stmt = base_stmt.where(MonthlySchedule.org_unit_id == org_unit_id)
    if status is not None:
        base_stmt = base_stmt.where(MonthlySchedule.status == status)

    total = db.scalar(
        select(func.count()).select_from(base_stmt.subquery())
    ) or 0

    stmt = base_stmt.options(
        selectinload(MonthlySchedule.org_unit),
        selectinload(MonthlySchedule.rule),
        selectinload(MonthlySchedule.days).options(
            selectinload(ScheduleDay.shifts).selectinload(ScheduleShift.persons)
        ),
    ).order_by(MonthlySchedule.id).offset(offset).limit(limit)

    schedules = list(db.scalars(stmt).all())
    return schedules, total


def get_schedule(db: Session, schedule_id: int) -> MonthlySchedule | None:
    return db.scalar(
        select(MonthlySchedule)
        .where(MonthlySchedule.id == schedule_id)
        .options(
            selectinload(MonthlySchedule.org_unit),
            selectinload(MonthlySchedule.rule),
            selectinload(MonthlySchedule.days).options(
                selectinload(ScheduleDay.shifts).selectinload(ScheduleShift.persons)
            ),
        )
    )


def get_schedule_days(
    db: Session,
    schedule_id: int,
    *,
    year: int | None = None,
    month: int | None = None,
) -> list[ScheduleDay]:
    stmt = (
        select(ScheduleDay)
        .where(ScheduleDay.schedule_id == schedule_id)
    )

    if year is not None and month is not None:
        stmt = stmt.where(extract("year", ScheduleDay.duty_date) == year)
        stmt = stmt.where(extract("month", ScheduleDay.duty_date) == month)

    stmt = stmt.options(
        selectinload(ScheduleDay.shifts).options(
            selectinload(ScheduleShift.shift_def),
            selectinload(ScheduleShift.persons).selectinload(ScheduleShiftPerson.person),
        )
    ).order_by(ScheduleDay.duty_date)

    return list(db.scalars(stmt).all())


def get_schedule_days_by_range(
    db: Session,
    schedule_id: int,
    *,
    from_date: date,
    to_date: date,
) -> list[ScheduleDay]:
    return list(
        db.scalars(
            select(ScheduleDay)
            .where(ScheduleDay.schedule_id == schedule_id)
            .where(ScheduleDay.duty_date >= from_date)
            .where(ScheduleDay.duty_date <= to_date)
            .options(
                selectinload(ScheduleDay.shifts).options(
                    selectinload(ScheduleShift.shift_def),
                    selectinload(ScheduleShift.persons).selectinload(ScheduleShiftPerson.person),
                )
            )
            .order_by(ScheduleDay.duty_date)
        ).all()
    )


def _load_holidays(db: Session, dates: list[date]) -> dict[date, str]:
    """批量加载法定节假日，返回 {date: holiday_name} 映射"""
    if not dates:
        return {}
    min_date = min(dates)
    max_date = max(dates)
    rows = db.scalars(
        select(HolidayCalendar)
        .where(HolidayCalendar.holiday_date >= min_date)
        .where(HolidayCalendar.holiday_date <= max_date)
        .where(HolidayCalendar.is_legal.is_(True))
        .where(HolidayCalendar.status == "enabled")
    ).all()
    return {row.holiday_date: row.holiday_name for row in rows}


def generate_schedule_from_rule(
    db: Session,
    rule: ShiftRule,
    version: ShiftRuleVersion,
    *,
    total_days: int = 365,
) -> int:
    """从已发布规则生成排班记录到 schedule_day / schedule_shift / schedule_shift_person。

    Returns: 生成的天数。
    """
    if rule.org_unit_id is None:
        return 0

    existing = db.scalars(
        select(MonthlySchedule).where(MonthlySchedule.org_unit_id == rule.org_unit_id)
    ).first()
    ms = existing or MonthlySchedule(
        org_unit_id=rule.org_unit_id,
        rule_id=rule.id,
        rule_version_id=version.id,
        status="draft",
        generated_at=datetime.now(),
    )
    if existing:
        ms.rule_version_id = version.id
        ms.generated_at = datetime.now()

    db.add(ms)
    db.flush()

    items = list(db.scalars(
        select(ShiftRuleItem)
        .where(ShiftRuleItem.version_id == version.id)
        .order_by(ShiftRuleItem.day_no)
    ).all())

    if not items:
        return 0

    rule_start = date.fromisoformat(rule.start_date)
    tomorrow = date.today() + timedelta(days=1)
    gen_start = rule_start
    gen_end = max(gen_start, tomorrow) + timedelta(days=total_days)

    all_dates = []
    current_date = gen_start
    while current_date <= gen_end:
        all_dates.append(current_date)
        current_date += timedelta(days=1)

    holiday_map = _load_holidays(db, all_dates)

    day_count = 0
    current_date = gen_start
    while current_date <= gen_end:
        cycle_index = (current_date - rule_start).days % rule.cycle_days
        item = items[cycle_index]

        existing_day = db.scalars(
            select(ScheduleDay).where(
                ScheduleDay.schedule_id == ms.id,
                ScheduleDay.duty_date == current_date,
            )
        ).first()
        if existing_day:
            if current_date < tomorrow:
                current_date += timedelta(days=1)
                continue
            db.delete(existing_day)

        sday = ScheduleDay(
            schedule_id=ms.id,
            duty_date=current_date,
            weekday=current_date.weekday(),
            is_legal_holiday=current_date in holiday_map,
            holiday_name=holiday_map.get(current_date),
        )
        db.add(sday)
        db.flush()

        for shift_def_id_str, person_ids in item.cell_persons.items():
            shift_def_id = int(shift_def_id_str)
            shift_def = db.get(ShiftDef, shift_def_id)
            if not shift_def:
                continue

            shift_start = datetime.combine(
                current_date,
                datetime.strptime(shift_def.start_time, "%H:%M").time(),
            )
            if shift_def.end_time == "24:00":
                shift_end = datetime.combine(current_date + timedelta(days=1), datetime.min.time())
            else:
                shift_end = datetime.combine(
                    current_date,
                    datetime.strptime(shift_def.end_time, "%H:%M").time(),
                )
            if shift_end <= shift_start:
                shift_end += timedelta(days=1)

            ss = ScheduleShift(
                schedule_day_id=sday.id,
                shift_def_id=shift_def_id,
                start_at=shift_start,
                end_at=shift_end,
                status="normal",
            )
            db.add(ss)
            db.flush()

            for pos, pid in enumerate(person_ids, 1):
                db.add(ScheduleShiftPerson(
                    schedule_shift_id=ss.id,
                    person_id=pid,
                    position_no=pos,
                    source_type="auto",
                ))

        day_count += 1
        current_date += timedelta(days=1)

    return day_count
