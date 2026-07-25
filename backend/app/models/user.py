from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import BaseModel

sys_user_role = Table(
    "sys_user_role",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("sys_user.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True),
)

sys_role_permission = Table(
    "sys_role_permission",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("sys_permission.id", ondelete="CASCADE"), primary_key=True),
)

sys_user_permission = Table(
    "sys_user_permission",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("sys_user.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", BigInteger, ForeignKey("sys_permission.id", ondelete="CASCADE"), primary_key=True),
)


class SysUser(BaseModel):
    __tablename__ = "sys_user"

    person_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("person.id", ondelete="SET NULL"), nullable=True,
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    wx_openid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roles: Mapped[list["SysRole"]] = relationship(secondary=sys_user_role, back_populates="users")
    direct_permissions: Mapped[list["SysPermission"]] = relationship(
        secondary=sys_user_permission, back_populates="direct_users",
    )

    __table_args__ = (
        UniqueConstraint("username", name="uq_sys_user_username"),
        UniqueConstraint("wx_openid", name="uq_sys_user_wx_openid"),
        UniqueConstraint("person_id", name="uq_sys_user_person_id"),
    )


class SysRole(BaseModel):
    __tablename__ = "sys_role"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    users: Mapped[list["SysUser"]] = relationship(secondary=sys_user_role, back_populates="roles")
    permissions: Mapped[list["SysPermission"]] = relationship(
        secondary=sys_role_permission, back_populates="roles",
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_sys_role_code"),
    )


class SysPermission(BaseModel):
    __tablename__ = "sys_permission"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    group_code: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    group_name: Mapped[str] = mapped_column(String(128), nullable=False, default="其他")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="enabled")

    roles: Mapped[list["SysRole"]] = relationship(
        secondary=sys_role_permission, back_populates="permissions",
    )
    direct_users: Mapped[list["SysUser"]] = relationship(
        secondary=sys_user_permission, back_populates="direct_permissions",
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_sys_permission_code"),
    )
