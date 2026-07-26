from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError
from app.models.holiday import HolidayCalendar
from app.models.person import Person
from app.models.schedule import (
    DutyChangeLedger,
    MonthlySchedule,
    ScheduleChangeLog,
    ScheduleDay,
    ScheduleRecalculationFlag,
    ScheduleShift,
    ScheduleShiftBaselinePerson,
    ScheduleShiftPerson,
)
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleItem, ShiftRuleVersion

SCHEDULE_MATERIALIZATION_DAYS = 365


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
    ).order_by(MonthlySchedule.id).offset(offset).limit(limit)

    schedules = list(db.scalars(stmt).all())
    return schedules, total


def get_schedule_counts(db: Session, schedule_ids: list[int]) -> dict[int, tuple[int, int, int, date | None]]:
    """Return summary counts without loading each schedule's day/shift tree."""
    if not schedule_ids:
        return {}
    day_counts = (
        select(
            ScheduleDay.schedule_id.label("schedule_id"),
            func.count().label("count"),
            func.max(ScheduleDay.duty_date).label("coverage_through"),
        )
        .where(ScheduleDay.schedule_id.in_(schedule_ids))
        .group_by(ScheduleDay.schedule_id)
        .subquery()
    )
    shift_counts = (
        select(ScheduleDay.schedule_id.label("schedule_id"), func.count().label("count"))
        .join(ScheduleShift, ScheduleShift.schedule_day_id == ScheduleDay.id)
        .where(ScheduleDay.schedule_id.in_(schedule_ids))
        .group_by(ScheduleDay.schedule_id)
        .subquery()
    )
    person_counts = (
        select(ScheduleDay.schedule_id.label("schedule_id"), func.count().label("count"))
        .join(ScheduleShift, ScheduleShift.schedule_day_id == ScheduleDay.id)
        .join(ScheduleShiftPerson, ScheduleShiftPerson.schedule_shift_id == ScheduleShift.id)
        .where(ScheduleDay.schedule_id.in_(schedule_ids))
        .group_by(ScheduleDay.schedule_id)
        .subquery()
    )
    rows = db.execute(
        select(
            MonthlySchedule.id,
            func.coalesce(day_counts.c.count, 0),
            day_counts.c.coverage_through,
            func.coalesce(shift_counts.c.count, 0),
            func.coalesce(person_counts.c.count, 0),
        )
        .where(MonthlySchedule.id.in_(schedule_ids))
        .outerjoin(day_counts, day_counts.c.schedule_id == MonthlySchedule.id)
        .outerjoin(shift_counts, shift_counts.c.schedule_id == MonthlySchedule.id)
        .outerjoin(person_counts, person_counts.c.schedule_id == MonthlySchedule.id)
    ).all()
    return {row[0]: (row[1], row[3], row[4], row[2]) for row in rows}


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
        month_start = date(year, month, 1)
        next_month_start = date(year + (month == 12), month % 12 + 1, 1)
        stmt = stmt.where(ScheduleDay.duty_date >= month_start).where(ScheduleDay.duty_date < next_month_start)

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


def get_legal_holidays(db: Session, dates: list[date]) -> dict[date, str]:
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


def update_schedule_shift_persons(
    db: Session, schedule: MonthlySchedule, shift: ScheduleShift, person_ids: list[int], remark: str | None,
    *, change_type: str = "manual", source_biz_no: str | None = None, actor_id: int | None = None,
    allowed_person_types: set[str] | None = None,
) -> ScheduleShift:
    """Replace one shift's final staff and append a traceable personnel ledger."""
    if not person_ids or len(person_ids) != len(set(person_ids)):
        raise BusinessRuleError(message="值班人员不能为空且不能重复")
    expected_count = db.scalar(
        select(func.count()).select_from(ScheduleShiftPerson)
        .where(ScheduleShiftPerson.schedule_shift_id == shift.id)
    ) or 0
    if len(person_ids) != expected_count:
        raise BusinessRuleError(message=f"值班人员数量必须保持为 {expected_count} 人")
    before_person_ids = list(db.scalars(
        select(ScheduleShiftPerson.person_id)
        .where(ScheduleShiftPerson.schedule_shift_id == shift.id)
        .order_by(ScheduleShiftPerson.position_no)
    ).all())
    if before_person_ids == person_ids:
        return shift
    persons = list(db.scalars(select(Person).where(Person.id.in_(person_ids))).all())
    allowed_person_types = allowed_person_types or {"duty_operator"}
    if len(persons) != len(person_ids) or any(
        p.org_unit_id != schedule.org_unit_id or p.status != "enabled"
        or (p.person_type == "duty_operator" and not p.participate_schedule)
        or p.person_type not in allowed_person_types
        for p in persons
    ):
        raise BusinessRuleError(message="值班人员不符合当前业务的机房、状态或人员类型要求")
    baseline_ids = list(db.scalars(
        select(ScheduleShiftBaselinePerson.person_id)
        .where(ScheduleShiftBaselinePerson.schedule_shift_id == shift.id)
        .order_by(ScheduleShiftBaselinePerson.position_no)
    ).all()) or before_person_ids
    next_version = schedule.version + 1
    db.add(ScheduleChangeLog(
        schedule_id=schedule.id, schedule_shift_id=shift.id, source_type="manual",
        schedule_version=next_version, before_person_ids=before_person_ids,
        after_person_ids=person_ids, remark=remark,
    ))
    db.query(ScheduleShiftPerson).filter(ScheduleShiftPerson.schedule_shift_id == shift.id).delete()
    for position_no, person_id in enumerate(person_ids, start=1):
        db.add(ScheduleShiftPerson(
            schedule_shift_id=shift.id, person_id=person_id, position_no=position_no,
            source_type=change_type, remark=remark,
        ))
    for position_no, (before_person_id, after_person_id) in enumerate(zip(before_person_ids, person_ids), start=1):
        if before_person_id != after_person_id:
            db.add(DutyChangeLedger(
                schedule_shift_id=shift.id,
                original_person_id=baseline_ids[position_no - 1] if position_no <= len(baseline_ids) else before_person_id,
                before_person_id=before_person_id,
                after_person_id=after_person_id,
                change_type=change_type,
                source_biz_no=source_biz_no,
                reason=remark,
                created_by=actor_id,
            ))
    schedule.version = next_version
    db.flush()
    return shift


def apply_historical_correction(
    db: Session, schedule: MonthlySchedule, shift: ScheduleShift, person_ids: list[int], reason: str, actor_id: int,
) -> ScheduleShift:
    if shift.schedule_day.duty_date >= date.today():
        raise BusinessRuleError(message="仅今天以前的班次可以执行历史修正")
    current_person_ids = list(db.scalars(
        select(ScheduleShiftPerson.person_id)
        .where(ScheduleShiftPerson.schedule_shift_id == shift.id)
        .order_by(ScheduleShiftPerson.position_no)
    ).all())
    if current_person_ids == person_ids:
        raise BusinessRuleError(message="修正后人员与当前最终排班一致")
    updated_shift = update_schedule_shift_persons(
        db, schedule, shift, person_ids, reason, change_type="historical_correction", actor_id=actor_id,
    )
    year_month = shift.schedule_day.duty_date.strftime("%Y-%m")
    flag = db.scalar(select(ScheduleRecalculationFlag).where(
        ScheduleRecalculationFlag.org_unit_id == schedule.org_unit_id,
        ScheduleRecalculationFlag.year_month == year_month,
    ))
    if flag is None:
        db.add(ScheduleRecalculationFlag(
            org_unit_id=schedule.org_unit_id, year_month=year_month,
            status="required", reason="历史最终排班已修正，需重新计算",
        ))
    else:
        flag.status = "required"
        flag.reason = "历史最终排班已修正，需重新计算"
    db.flush()
    return updated_shift


def generate_schedule_from_rule(
    db: Session,
    rule: ShiftRule,
    version: ShiftRuleVersion,
    *,
    total_days: int | None = None,
    through_date: date | None = None,
) -> int:
    """将已发布规则物化到指定日期，或保持未来一年的滚动覆盖。

    ``total_days`` 仅保留给边界测试使用，生产调用以 ``through_date`` 或默认
    滚动覆盖范围决定终止日期。

    Returns: 新增的天数。
    """
    if rule.org_unit_id is None:
        return 0

    existing = db.scalars(
        select(MonthlySchedule)
        .where(MonthlySchedule.org_unit_id == rule.org_unit_id)
        .with_for_update()
    ).first()
    same_version = (
        existing is not None
        and existing.rule_id == rule.id
        and existing.rule_version_id == version.id
    )
    generated_at = datetime.now()
    ms = existing or MonthlySchedule(
        org_unit_id=rule.org_unit_id,
        rule_id=rule.id,
        rule_version_id=version.id,
        status="published",
        generated_at=generated_at,
        published_at=generated_at,
    )
    if existing is not None and not same_version:
        # These references are a pair: a version must belong to its rule.
        ms.rule_id = rule.id
        ms.rule_version_id = version.id
        ms.status = "published"
        ms.generated_at = generated_at
        ms.published_at = generated_at
    db.add(ms)
    db.flush()

    items = list(db.scalars(
        select(ShiftRuleItem)
        .where(ShiftRuleItem.version_id == version.id)
        .order_by(ShiftRuleItem.day_no)
    ).all())

    cycle_days = version.cycle_days
    items_by_day = {item.day_no: item for item in items}
    if cycle_days < 1 or set(items_by_day) != set(range(1, cycle_days + 1)):
        raise BusinessRuleError(message="排班规则版本的周期天数与排班项不一致，请重新保存规则")

    rule_start = date.fromisoformat(version.start_date)
    tomorrow = date.today() + timedelta(days=1)
    default_end = max(rule_start, tomorrow) + timedelta(days=SCHEDULE_MATERIALIZATION_DAYS)
    if total_days is not None:
        gen_end = max(rule_start, tomorrow) + timedelta(days=total_days)
    else:
        gen_end = max(default_end, through_date or default_end)

    existing_days: dict[date, ScheduleDay] = {}
    if same_version or existing is None:
        existing_days = {
            day.duty_date: day
            for day in db.scalars(
                select(ScheduleDay)
                .where(ScheduleDay.schedule_id == ms.id)
                .where(ScheduleDay.duty_date >= rule_start)
                .where(ScheduleDay.duty_date <= gen_end)
            ).all()
        }
    elif existing:
        # A newly published version replaces its effective range, while dates before
        # its start remain historical records.
        for existing_day in db.scalars(
            select(ScheduleDay)
            .where(ScheduleDay.schedule_id == ms.id)
            .where(ScheduleDay.duty_date >= rule_start)
        ).all():
            db.delete(existing_day)
        db.flush()

    dates_to_generate = []
    current_date = rule_start
    while current_date <= gen_end:
        if current_date not in existing_days:
            dates_to_generate.append(current_date)
        current_date += timedelta(days=1)

    holiday_map = get_legal_holidays(db, dates_to_generate)
    shift_def_ids = {
        int(shift_def_id)
        for item in items
        for shift_def_id in item.cell_persons
    }
    shift_defs = {
        shift_def.id: shift_def
        for shift_def in db.scalars(select(ShiftDef).where(ShiftDef.id.in_(shift_def_ids))).all()
    }
    invalid_shift_def_ids = sorted(
        shift_def_id
        for shift_def_id in shift_def_ids
        if (
            shift_def_id not in shift_defs
            or shift_defs[shift_def_id].org_unit_id != rule.org_unit_id
            or shift_defs[shift_def_id].status != "enabled"
        )
    )
    if invalid_shift_def_ids:
        raise BusinessRuleError(
            message=f"规则包含不属于当前机房的启用班次: {invalid_shift_def_ids}",
        )

    day_count = 0
    for current_date in dates_to_generate:
        cycle_index = (current_date - rule_start).days % cycle_days
        item = items_by_day[cycle_index + 1]

        sday = ScheduleDay(
            schedule_id=ms.id,
            duty_date=current_date,
            weekday=current_date.weekday(),
            is_legal_holiday=current_date in holiday_map,
            holiday_name=holiday_map.get(current_date),
        )
        for shift_def_id_str, person_ids in item.cell_persons.items():
            shift_def_id = int(shift_def_id_str)
            shift_def = shift_defs.get(shift_def_id)
            if not shift_def:
                raise BusinessRuleError(message=f"规则包含不存在的班次: {shift_def_id}")

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
                shift_def_id=shift_def_id,
                start_at=shift_start,
                end_at=shift_end,
                status="normal",
            )
            for pos, pid in enumerate(person_ids, 1):
                ss.persons.append(ScheduleShiftPerson(
                    person_id=pid,
                    position_no=pos,
                    source_type="auto",
                ))
                ss.baseline_persons.append(ScheduleShiftBaselinePerson(person_id=pid, position_no=pos))
            sday.shifts.append(ss)

        db.add(sday)

        day_count += 1

    if existing and (not same_version or day_count):
        ms.rule_id = rule.id
        ms.rule_version_id = version.id
        ms.status = "published"
        ms.generated_at = generated_at
        ms.published_at = generated_at

    db.flush()
    return day_count
