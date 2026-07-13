from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson


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
