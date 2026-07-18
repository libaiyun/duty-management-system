from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, _utcnow


class ApprovalTask(BaseModel):
    __tablename__ = "approval_task"

    org_unit_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("org_unit.id", ondelete="RESTRICT"), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    node_code: Mapped[str] = mapped_column(String(64), nullable=False)
    assignee_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignee = relationship("SysUser", foreign_keys=[assignee_user_id])
    records = relationship(
        "ApprovalRecord", back_populates="task", order_by="ApprovalRecord.operated_at",
    )

    __table_args__ = (
        Index("ix_approval_task_assignee_status", "assignee_user_id", "status"),
        Index("ix_approval_task_org_status", "org_unit_id", "status"),
        Index("ix_approval_task_org_status_arrived", "org_unit_id", "status", "arrived_at"),
    )


class ApprovalRecord(BaseModel):
    __tablename__ = "approval_record"

    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("approval_task.id", ondelete="RESTRICT"), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    biz_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    operator_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id", ondelete="RESTRICT"), nullable=False)
    opinion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    operated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict,
    )

    task = relationship("ApprovalTask", back_populates="records")
    operator = relationship("SysUser", foreign_keys=[operator_user_id])

    __table_args__ = (Index("ix_approval_record_task_operated", "task_id", "operated_at"),)
