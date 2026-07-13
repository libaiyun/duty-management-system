from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import BaseModel


class ShiftDef(BaseModel):
    __tablename__ = "shift_def"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    display_order: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")


class ShiftRule(BaseModel):
    __tablename__ = "shift_rule"

    org_unit_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("org_unit.id", ondelete="SET NULL"), nullable=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    cycle_days: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    persons_per_cell: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    org_unit = relationship("OrgUnit", backref="shift_rules", foreign_keys=[org_unit_id])
    versions = relationship(
        "ShiftRuleVersion",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="ShiftRuleVersion.version_no",
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_shift_rule_code"),
    )


class ShiftRuleVersion(BaseModel):
    __tablename__ = "shift_rule_version"

    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shift_rule.id", ondelete="CASCADE"), nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    persons_per_cell: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    rule = relationship("ShiftRule", back_populates="versions", foreign_keys=[rule_id])
    items = relationship(
        "ShiftRuleItem",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="ShiftRuleItem.day_no",
    )

    __table_args__ = (
        UniqueConstraint("rule_id", "version_no", name="uq_shift_rule_version"),
    )


class ShiftRuleItem(BaseModel):
    __tablename__ = "shift_rule_item"

    version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shift_rule_version.id", ondelete="CASCADE"), nullable=False,
    )
    day_no: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_persons: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict)

    version = relationship("ShiftRuleVersion", back_populates="items", foreign_keys=[version_id])
