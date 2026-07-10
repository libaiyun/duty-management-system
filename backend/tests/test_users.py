import pytest
from fastapi.testclient import TestClient

from app.models.user import SysPermission, SysRole
from app.services.auth import create_user

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session) -> tuple[int, str]:
    user = create_user(db_session, "admin", "password123", "管理员")
    perm = SysPermission(code="system:user:manage", name="Manage Users", type="api")
    role = SysRole(code="admin-role", name="Admin Role")
    role.permissions.append(perm)
    db_session.add_all([perm, role])
    user.roles.append(role)
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    return user.id, token


class TestUserApi:
    def test_get_users_list(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_create_user(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/users",
            json={"username": "newuser", "password": "pass123", "display_name": "新用户"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "newuser"
        assert data["display_name"] == "新用户"
        assert data["status"] == "enabled"

    def test_get_user_detail(self, api_client: TestClient, db_session) -> None:
        admin_id, token = _create_admin(api_client, db_session)
        resp = api_client.get(f"/api/v1/users/{admin_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "admin"
        assert len(data["role_ids"]) >= 1

    def test_update_user_status(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/users",
            json={"username": "user2", "password": "pass", "display_name": "用户2"},
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/users/{user_id}",
            json={"status": "disabled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "disabled"

    def test_assign_user_roles(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        role = SysRole(code="test-role", name="Test Role")
        db_session.add(role)
        db_session.commit()

        resp = api_client.post(
            "/api/v1/users",
            json={"username": "user3", "password": "pass", "display_name": "用户3"},
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/users/{user_id}/roles",
            json={"role_ids": [role.id]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_users_requires_permission(self, api_client: TestClient, db_session) -> None:
        user = create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")

        resp = api_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestRoleApi:
    def test_create_role(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)

        resp = api_client.post(
            "/api/v1/roles",
            json={"code": "viewer", "name": "查看者", "remark": "只读"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "viewer"
        assert data["name"] == "查看者"

    def test_list_roles(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)

        resp = api_client.get("/api/v1/roles", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_get_permissions(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)

        resp = api_client.get("/api/v1/permissions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
