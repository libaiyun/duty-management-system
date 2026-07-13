from datetime import date

from sqlalchemy import Boolean, Date, Integer, String, UniqueConstraint
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
