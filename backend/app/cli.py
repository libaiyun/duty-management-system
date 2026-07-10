"""CLI commands for system administration.

Usage:
    python -m app.cli create-admin --username admin --password admin123 [--display-name 管理员]
"""

import argparse
import sys

from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user

ALL_PERMISSION_CODES = (
    "duty:schedule:view_self",
    "duty:swap:view_self",
    "duty:leave:view_self",
    "duty:cover:view_self",
    "approval:task:view_todo",
    "approval:record:view_done",
    "schedule:monthly:view",
    "schedule:detail:view",
    "duty:actual:view",
    "leave:record:view",
    "cover:assignment:view",
    "refund:batch:calculate",
    "refund:detail:view",
    "attendance:monthly:view",
    "export:task:view",
    "org:unit:view",
    "person:manage:view",
    "shift:rule:view",
    "holiday:standard:view",
    "system:user:manage",
    "system:log:view",
    "system:backup:view",
)


def _seed_permissions(db: Session) -> None:
    existing = {row[0] for row in db.query(SysPermission.code).all()}
    for code in ALL_PERMISSION_CODES:
        if code not in existing:
            db.add(SysPermission(code=code, name=code, type="api"))
    db.flush()


def _get_or_create_admin_role(db: Session) -> SysRole:
    role = db.query(SysRole).filter(SysRole.code == "super-admin").first()
    if role is None:
        role = SysRole(code="super-admin", name="超级管理员", remark="拥有所有权限")
        db.add(role)
        db.flush()
    assert role is not None
    all_perms: list[SysPermission] = db.query(SysPermission).all()
    role.permissions = all_perms  # type: ignore[assignment]
    db.flush()
    return role


def cmd_create_admin(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        _seed_permissions(db)
        role = _get_or_create_admin_role(db)
        user = create_user(db, args.username, args.password, args.display_name)
        user.roles.append(role)
        db.commit()
        print(f"Admin user created: id={user.id}, username={user.username}")
    except IntegrityError:
        db.rollback()
        print(f"Error: username '{args.username}' already exists", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Duty Management System CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    admin_parser = subparsers.add_parser("create-admin", help="创建初始管理员")
    admin_parser.add_argument("--username", required=True, help="登录名")
    admin_parser.add_argument("--password", required=True, help="密码")
    admin_parser.add_argument("--display-name", default="管理员", help="显示名称")

    args = parser.parse_args()

    if args.command == "create-admin":
        cmd_create_admin(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
