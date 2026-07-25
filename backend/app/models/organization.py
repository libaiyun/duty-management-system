from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrgUnit(BaseModel):
    __tablename__ = "org_unit"

    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("org_unit.id", ondelete="SET NULL"), nullable=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    manager_person_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("person.id", ondelete="SET NULL", name="fk_org_unit_manager_person", use_alter=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")
    sort_order: Mapped[int] = mapped_column(default=0)

    parent = relationship("OrgUnit", remote_side=lambda: OrgUnit.id, back_populates="children")
    children = relationship("OrgUnit", back_populates="parent", order_by="OrgUnit.sort_order")

    __table_args__ = (
        UniqueConstraint("code", name="uq_org_unit_code"),
    )
