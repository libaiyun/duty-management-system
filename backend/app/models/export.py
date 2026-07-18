from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ExportTask(BaseModel):
    """A generated, downloadable business export."""

    __tablename__ = "export_task"

    org_unit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("org_unit.id", ondelete="RESTRICT"),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    org_unit = relationship("OrgUnit", foreign_keys=[org_unit_id])

    __table_args__ = (
        Index("ix_export_task_org_created", "org_unit_id", "created_at"),
        Index("ix_export_task_status", "status"),
    )
