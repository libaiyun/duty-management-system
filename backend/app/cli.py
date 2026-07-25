"""CLI commands for system administration.

Usage:
    python -m app.cli create-admin --username admin --password admin123 [--display-name 管理员]
"""

import argparse
import sys

from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.services.auth import create_user, seed_permission_system


def cmd_create_admin(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        seed_permission_system(db)
        user = create_user(db, args.username, args.password, args.display_name, is_superuser=True)
        db.flush()
        db.commit()
        print(f"Admin user created: id={user.id}, username={user.username}")
    except IntegrityError:
        # 唯一冲突只可能是 username（权限/角色 code 由本脚本生成不冲突）
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
