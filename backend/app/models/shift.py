from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    station_type: Mapped[str] = mapped_column(String(64), nullable=False)
    persons_per_shift: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, default="broadcast_fixed")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    org_unit = relationship("OrgUnit", backref="shift_rules", foreign_keys=[org_unit_id])
    items = relationship(
        "ShiftRuleItem",
        back_populates="rule",
        cascade="all, delete-orphan",
        order_by="ShiftRuleItem.sequence_no",
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_shift_rule_code"),
    )


class ShiftRuleItem(BaseModel):
    __tablename__ = "shift_rule_item"

    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shift_rule.id", ondelete="CASCADE"), nullable=False,
    )
    group_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shift_code: Mapped[str] = mapped_column(String(32), nullable=False)
    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    rule = relationship("ShiftRule", back_populates="items", foreign_keys=[rule_id])
