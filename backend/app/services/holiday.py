from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, StateConflictError
from app.models.holiday import HolidayCalendar

# 首期固定业务标准（总体设计 §12.2），首期只读展示
FIXED_SUBSIDY_STANDARD = {
    "early_meal": 10,
    "middle_meal": 10,
    "night_meal": 14,
    "meal_refund_night_to_middle": 4,
    "holiday_overtime": 150,
    "holiday_overtime_refund_night_to_middle": 56,
}


def list_holidays(db: Session, year: int | None = None) -> list[HolidayCalendar]:
    stmt = select(HolidayCalendar)
    if year is not None:
        stmt = stmt.where(HolidayCalendar.year == year)
    stmt = stmt.order_by(HolidayCalendar.holiday_date)
    return list(db.scalars(stmt).all())


def get_holiday(db: Session, holiday_id: int) -> HolidayCalendar | None:
    return db.get(HolidayCalendar, holiday_id)


def _new_holiday(
    holiday_date: date,
    holiday_name: str,
    is_legal: bool,
    remark: str | None,
) -> HolidayCalendar:
    return HolidayCalendar(
        holiday_date=holiday_date,
        holiday_name=holiday_name,
        year=holiday_date.year,
        is_legal=is_legal,
        remark=remark,
    )


def create_holiday(
    db: Session,
    holiday_date: date,
    holiday_name: str,
    is_legal: bool = True,
    remark: str | None = None,
) -> HolidayCalendar:
    existing = db.scalars(
        select(HolidayCalendar).where(HolidayCalendar.holiday_date == holiday_date)
    ).first()
    if existing:
        raise StateConflictError(message=f"日期 {holiday_date.isoformat()} 的节假日已存在")
    holiday = _new_holiday(holiday_date, holiday_name, is_legal, remark)
    db.add(holiday)
    db.flush()
    return holiday


def update_holiday(
    db: Session,
    holiday_id: int,
    holiday_name: str | None = None,
    is_legal: bool | None = None,
    status: str | None = None,
    remark: str | None = None,
) -> HolidayCalendar:
    holiday = db.get(HolidayCalendar, holiday_id)
    if holiday is None:
        raise NotFoundError(message="节假日不存在")
    if holiday_name is not None:
        holiday.holiday_name = holiday_name
    if is_legal is not None:
        holiday.is_legal = is_legal
    if status is not None:
        holiday.status = status
    if remark is not None:
        holiday.remark = remark
    db.flush()
    return holiday


def delete_holiday(db: Session, holiday_id: int) -> None:
    holiday = db.get(HolidayCalendar, holiday_id)
    if holiday is None:
        raise NotFoundError(message="节假日不存在")
    db.delete(holiday)
    db.flush()


def import_holidays(
    db: Session,
    items: list[tuple[date, str, bool, str | None]],
) -> tuple[int, int, list[date]]:
    """批量导入节假日。已存在日期跳过，返回 (创建数, 跳过数, 跳过日期列表)。"""
    existing_dates = set(
        db.scalars(select(HolidayCalendar.holiday_date)).all()
    )
    created = 0
    skipped_dates: list[date] = []
    seen: set[date] = set()
    for holiday_date, holiday_name, is_legal, remark in items:
        if holiday_date in existing_dates or holiday_date in seen:
            skipped_dates.append(holiday_date)
            continue
        seen.add(holiday_date)
        db.add(_new_holiday(holiday_date, holiday_name, is_legal, remark))
        created += 1
    db.flush()
    return created, len(skipped_dates), skipped_dates


def get_subsidy_standard() -> dict[str, int]:
    return dict(FIXED_SUBSIDY_STANDARD)
