import pytest
from fastapi.testclient import TestClient

from app.models.shift import ShiftDef
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session) -> tuple[int, str]:
    user = create_user(db_session, "admin", "password123", "管理员")
    perm = SysPermission(code="shift:rule:view", name="View Shift Rule", type="api")
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.append(perm)
    db_session.add_all([perm, role])
    user.roles.append(role)
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    return user.id, token


class TestShiftDefApi:
    def test_list_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/shifts", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create_shift(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shifts",
            json={"code": "early", "name": "早班", "start_time": "00:00", "end_time": "08:00", "display_order": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "early"
        assert data["name"] == "早班"
        assert data["start_time"] == "00:00"
        assert data["end_time"] == "08:00"
        assert data["display_order"] == 1
        assert data["status"] == "enabled"

    def test_create_multiple_shifts(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        shifts = [
            ("early", "早班", "00:00", "08:00", 1),
            ("middle", "中班", "08:00", "16:00", 2),
            ("night", "晚班", "16:00", "24:00", 3),
        ]
        for code, name, start, end, order in shifts:
            resp = api_client.post(
                "/api/v1/shifts",
                json={"code": code, "name": name, "start_time": start, "end_time": end, "display_order": order},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, f"Failed to create {name}"

        resp = api_client.get("/api/v1/shifts", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 3

    def test_get_shift_detail(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shifts",
            json={"code": "night", "name": "晚班", "start_time": "16:00", "end_time": "24:00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        shift_id = resp.json()["data"]["id"]

        resp = api_client.get(f"/api/v1/shifts/{shift_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "晚班"

    def test_update_shift(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shifts",
            json={"code": "test", "name": "测试班", "start_time": "06:00", "end_time": "10:00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        shift_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/shifts/{shift_id}",
            json={"name": "测试班(改)", "status": "disabled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "测试班(改)"
        assert data["status"] == "disabled"

    def test_shift_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/shifts/99999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_duplicate_code(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/shifts",
            json={"code": "early", "name": "早班", "start_time": "00:00", "end_time": "08:00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/shifts",
            json={"code": "early", "name": "早班重复", "start_time": "10:00", "end_time": "14:00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_time_overlap(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/shifts",
            json={"code": "early", "name": "早班", "start_time": "00:00", "end_time": "08:00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/shifts",
            json={"code": "overlap", "name": "重叠班", "start_time": "06:00", "end_time": "10:00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_update_time_overlap(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/shifts",
            json={"code": "early", "name": "早班", "start_time": "00:00", "end_time": "08:00", "display_order": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/shifts",
            json={"code": "middle", "name": "中班", "start_time": "08:00", "end_time": "16:00", "display_order": 2},
            headers={"Authorization": f"Bearer {token}"},
        )
        shift_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/shifts/{shift_id}",
            json={"start_time": "06:00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_requires_permission(self, api_client: TestClient, db_session) -> None:
        user = create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")

        resp = api_client.get("/api/v1/shifts", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestShiftDefModel:
    def test_default_values(self, db_session) -> None:
        sd = ShiftDef(code="early", name="早班", start_time="00:00", end_time="08:00")
        db_session.add(sd)
        db_session.commit()

        assert sd.status == "enabled"
        assert sd.display_order == 0

    def test_unique_code(self, db_session) -> None:
        db_session.add(ShiftDef(code="early", name="早班", start_time="00:00", end_time="08:00"))
        db_session.commit()
        db_session.add(ShiftDef(code="early", name="早班重复", start_time="10:00", end_time="14:00"))
        with pytest.raises(Exception):
            db_session.commit()
