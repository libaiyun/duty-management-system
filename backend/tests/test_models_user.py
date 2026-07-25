from datetime import UTC, datetime

import pytest
from app.models.user import (
    SysPermission,
    SysRole,
    SysUser,
    sys_role_permission,
    sys_user_role,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def session(db_session: Session) -> Session:
    return db_session


def test_create_user(session: Session) -> None:
    user = SysUser(username="admin", password_hash="hash123", display_name="管理员")
    session.add(user)
    session.flush()

    assert user.id is not None
    assert user.created_at is not None
    assert user.version == 1
    assert user.status == "enabled"


def test_user_unique_username(session: Session) -> None:
    session.add(SysUser(username="admin", password_hash="a", display_name="A"))
    session.flush()

    session.add(SysUser(username="admin", password_hash="b", display_name="B"))
    with pytest.raises(Exception):
        session.flush()


def test_create_role(session: Session) -> None:
    role = SysRole(code="admin", name="系统管理员")
    session.add(role)
    session.flush()

    assert role.id is not None
    assert role.status == "enabled"


def test_role_unique_code(session: Session) -> None:
    session.add(SysRole(code="admin", name="A"))
    session.flush()

    session.add(SysRole(code="admin", name="B"))
    with pytest.raises(Exception):
        session.flush()


def test_create_permission(session: Session) -> None:
    perm = SysPermission(code="system:user:manage", name="管理用户", type="api")
    session.add(perm)
    session.flush()

    assert perm.id is not None
    assert perm.status == "enabled"


def test_assign_role_to_user(session: Session) -> None:
    user = SysUser(username="user1", password_hash="h", display_name="User1")
    role = SysRole(code="admin", name="Admin")
    session.add_all([user, role])
    session.flush()

    user.roles.append(role)
    session.flush()

    stmt = select(sys_user_role)
    rows = session.execute(stmt).all()
    assert len(rows) == 1
    assert rows[0].user_id == user.id
    assert rows[0].role_id == role.id


def test_assign_permission_to_role(session: Session) -> None:
    role = SysRole(code="admin", name="Admin")
    perm = SysPermission(code="system:user:manage", name="Manage Users", type="api")
    session.add_all([role, perm])
    session.flush()

    role.permissions.append(perm)
    session.flush()

    stmt = select(sys_role_permission)
    rows = session.execute(stmt).all()
    assert len(rows) == 1
    assert rows[0].role_id == role.id
    assert rows[0].permission_id == perm.id


def test_user_role_cascade_delete(session: Session) -> None:
    user = SysUser(username="u", password_hash="h", display_name="U")
    role = SysRole(code="r", name="R")
    session.add_all([user, role])
    session.flush()
    user.roles.append(role)
    session.flush()

    session.delete(user)
    session.flush()

    stmt = select(sys_user_role)
    assert len(session.execute(stmt).all()) == 0


def test_role_permission_cascade_delete(session: Session) -> None:
    role = SysRole(code="r", name="R")
    perm = SysPermission(code="p", name="P", type="menu")
    session.add_all([role, perm])
    session.flush()
    role.permissions.append(perm)
    session.flush()

    session.delete(role)
    session.flush()

    stmt = select(sys_role_permission)
    assert len(session.execute(stmt).all()) == 0


def test_soft_delete_user(session: Session) -> None:
    user = SysUser(username="u", password_hash="h", display_name="U")
    session.add(user)
    session.flush()

    assert user.deleted_at is None
    user.deleted_at = datetime.now(UTC)
    session.flush()
    assert user.deleted_at is not None


def test_user_default_values(session: Session) -> None:
    user = SysUser(username="u", password_hash="h", display_name="U")
    session.add(user)
    session.flush()

    assert user.status == "enabled"
    assert user.version == 1
    assert user.last_login_at is None
    assert user.wx_openid is None
    assert user.person_id is None


def test_permission_hierarchy(session: Session) -> None:
    parent = SysPermission(code="system", name="系统管理", type="menu")
    session.add(parent)
    session.flush()

    child = SysPermission(
        code="system:user:manage", name="管理用户", type="api", parent_id=parent.id, path="/system/users", action="manage",
    )
    session.add(child)
    session.flush()

    assert child.parent_id == parent.id
    assert child.path == "/system/users"
    assert child.action == "manage"
