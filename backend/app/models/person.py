from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Person(BaseModel):
    __tablename__ = "person"

    org_unit_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("org_unit.id", ondelete="SET NULL"), nullable=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    person_type: Mapped[str] = mapped_column(String(32), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    participate_schedule: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)

    org_unit = relationship("OrgUnit", backref="persons", foreign_keys=[org_unit_id])
    account = relationship("SysUser", foreign_keys="SysUser.person_id", uselist=False)

    @property
    def account_bound(self) -> bool:
        return self.account is not None

    @property
    def account_username(self) -> str | None:
        return self.account.username if self.account is not None else None

    __table_args__ = (
        UniqueConstraint("code", name="uq_person_code"),
    )
