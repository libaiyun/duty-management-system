from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class MonthlySchedule(BaseModel):
    __tablename__ = "monthly_schedule"

    org_unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("org_unit.id", ondelete="RESTRICT"), nullable=False,
    )
    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shift_rule.id", ondelete="RESTRICT"), nullable=False,
    )
    rule_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shift_rule_version.id", ondelete="RESTRICT"), nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft",
    )
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)

    org_unit = relationship("OrgUnit", backref="monthly_schedules", foreign_keys=[org_unit_id])
    rule = relationship("ShiftRule", backref="monthly_schedules", foreign_keys=[rule_id])
    rule_version = relationship("ShiftRuleVersion", foreign_keys=[rule_version_id])
    days = relationship(
        "ScheduleDay",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleDay.duty_date",
    )

    __table_args__ = (
        Index(
            "uq_monthly_schedule_org",
            "org_unit_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )


class ScheduleDay(BaseModel):
    __tablename__ = "schedule_day"

    schedule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monthly_schedule.id", ondelete="CASCADE"), nullable=False,
    )
    duty_date: Mapped[date] = mapped_column(Date, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    is_legal_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    holiday_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    schedule = relationship("MonthlySchedule", back_populates="days", foreign_keys=[schedule_id])
    shifts = relationship(
        "ScheduleShift",
        back_populates="schedule_day",
        cascade="all, delete-orphan",
        order_by="ScheduleShift.start_at",
    )

    __table_args__ = (
        Index("ix_schedule_day_schedule_id", "schedule_id"),
        Index("ix_schedule_day_duty_date", "duty_date"),
    )


class ScheduleShift(BaseModel):
    __tablename__ = "schedule_shift"

    schedule_day_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schedule_day.id", ondelete="CASCADE"), nullable=False,
    )
    shift_def_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shift_def.id", ondelete="RESTRICT"), nullable=False,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")

    schedule_day = relationship("ScheduleDay", back_populates="shifts", foreign_keys=[schedule_day_id])
    shift_def = relationship("ShiftDef", foreign_keys=[shift_def_id])
    persons = relationship(
        "ScheduleShiftPerson",
        back_populates="schedule_shift",
        cascade="all, delete-orphan",
        order_by="ScheduleShiftPerson.position_no",
    )

    __table_args__ = (
        Index("ix_schedule_shift_day", "schedule_day_id"),
    )


class ScheduleShiftPerson(BaseModel):
    __tablename__ = "schedule_shift_person"

    schedule_shift_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schedule_shift.id", ondelete="CASCADE"), nullable=False,
    )
    person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False,
    )
    position_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    schedule_shift = relationship("ScheduleShift", back_populates="persons", foreign_keys=[schedule_shift_id])
    person = relationship("Person", foreign_keys=[person_id])

    __table_args__ = (
        Index("ix_schedule_shift_person_shift", "schedule_shift_id"),
    )
