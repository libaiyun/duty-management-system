from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HolidayCalendar(BaseModel):
    __tablename__ = "holiday_calendar"

    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    holiday_name: Mapped[str] = mapped_column(String(64), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_legal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("holiday_date", name="uq_holiday_calendar_date"),
    )


class RefundStandard(BaseModel):
    __tablename__ = "refund_standard"

    org_unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("org_unit.id", ondelete="RESTRICT"), nullable=False,
    )
    meal_early: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=10)
    meal_middle: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=10)
    meal_night: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=14)
    meal_refund: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=4)
    holiday_overtime: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=150)
    holiday_refund: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=56)

    __table_args__ = (
        UniqueConstraint("org_unit_id", name="uq_refund_standard_org"),
    )
