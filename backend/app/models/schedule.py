from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

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
        Index("ix_schedule_day_schedule_date_lookup", "schedule_id", "duty_date"),
        Index(
            "uq_schedule_day_schedule_date",
            "schedule_id",
            "duty_date",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
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


class ActualDuty(BaseModel):
    """Published duty result; later swap/leave/cover workflows amend these rows."""

    __tablename__ = "actual_duty"

    org_unit_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("org_unit.id", ondelete="RESTRICT"), nullable=False,
    )
    schedule_shift_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schedule_shift.id", ondelete="RESTRICT"), nullable=False,
    )
    original_person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False,
    )
    actual_person_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False,
    )
    duty_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_def_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shift_def.id", ondelete="RESTRICT"), nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="schedule")
    source_record_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    schedule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    org_unit = relationship("OrgUnit", foreign_keys=[org_unit_id])
    schedule_shift = relationship("ScheduleShift", foreign_keys=[schedule_shift_id])
    original_person = relationship("Person", foreign_keys=[original_person_id])
    actual_person = relationship("Person", foreign_keys=[actual_person_id])
    shift_def = relationship("ShiftDef", foreign_keys=[shift_def_id])

    __table_args__ = (
        Index("ix_actual_duty_org_date", "org_unit_id", "duty_date"),
        Index("ix_actual_duty_person_date", "actual_person_id", "duty_date"),
        Index("ix_actual_duty_shift_date", "shift_def_id", "duty_date"),
        Index("uq_actual_duty_shift_original", "schedule_shift_id", "original_person_id", unique=True),
    )


class ShiftSwap(BaseModel):
    """A requested mutual swap or one-way cover for published duties."""

    __tablename__ = "shift_swap"
    biz_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    swap_type: Mapped[str] = mapped_column(String(32), nullable=False)
    applicant_person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False)
    source_shift_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("schedule_shift.id", ondelete="RESTRICT"), nullable=False)
    target_person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("person.id", ondelete="RESTRICT"), nullable=False)
    target_shift_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("schedule_shift.id", ondelete="RESTRICT"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applicant = relationship("Person", foreign_keys=[applicant_person_id])
    target_person = relationship("Person", foreign_keys=[target_person_id])
    source_shift = relationship("ScheduleShift", foreign_keys=[source_shift_id])
    target_shift = relationship("ScheduleShift", foreign_keys=[target_shift_id])
    __table_args__ = (Index("ix_shift_swap_applicant_status", "applicant_person_id", "status"), Index("ix_shift_swap_target_status", "target_person_id", "status"))


class ScheduleChangeLog(BaseModel):
    """Immutable record of one manual staffing adjustment."""

    __tablename__ = "schedule_change_log"

    schedule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monthly_schedule.id", ondelete="CASCADE"), nullable=False,
    )
    schedule_shift_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("schedule_shift.id", ondelete="CASCADE"), nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    schedule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    before_person_ids: Mapped[list[int]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    after_person_ids: Mapped[list[int]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    schedule = relationship("MonthlySchedule", foreign_keys=[schedule_id])
    schedule_shift = relationship("ScheduleShift", foreign_keys=[schedule_shift_id])

    __table_args__ = (
        Index("ix_schedule_change_log_schedule_shift", "schedule_id", "schedule_shift_id"),
    )
