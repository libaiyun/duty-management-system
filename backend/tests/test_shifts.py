import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.shift import ShiftDef
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.user import SysDataScope, SysPermission, SysRole
from app.services.auth import create_user

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session) -> tuple[int, str]:
    room = OrgUnit(code="room-1", name="测试机房", type="room")
    db_session.add(room)
    db_session.flush()
    person = Person(code="P001", name="管理员", person_type="director", org_unit_id=room.id)
    db_session.add(person)
    db_session.flush()
    user = create_user(db_session, "admin", "password123", "管理员")
    user.person_id = person.id
    permissions = [
        SysPermission(code="shift:def:view", name="View Shift", type="api"),
        SysPermission(code="shift:def:manage", name="Manage Shift", type="api"),
    ]
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.extend(permissions)
    db_session.add_all([*permissions, role])
    user.roles.append(role)
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    return user.id, token


class TestShiftDefApi:
    def test_global_scope_requires_selected_room(self, api_client: TestClient, db_session) -> None:
        room = OrgUnit(code="room-1", name="测试机房", type="room")
        db_session.add(room)
        user = create_user(db_session, "global-admin", "password123", "管理员")
        permission = SysPermission(code="shift:def:view", name="View Shift", type="api")
        role = SysRole(code="global-role", name="Global")
        role.permissions.append(permission)
        user.roles.append(role)
        db_session.add_all([permission, role, SysDataScope(user_id=user.id, scope_type="all")])
        db_session.commit()
        token = _login(api_client, db_session, "global-admin", "password123")

        missing = api_client.get("/api/v1/shifts", headers={"Authorization": f"Bearer {token}"})
        assert missing.status_code == 422
        assert missing.json()["code"] == "ADMIN_NO_ROOM_SELECTED"

        selected = api_client.get(
            "/api/v1/shifts",
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room.id)},
        )
        assert selected.status_code == 200

    def test_list_initializes_default_shifts_for_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/shifts", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert [
            (shift["code"], shift["name"], shift["start_time"], shift["end_time"], shift["display_order"])
            for shift in resp.json()["data"]
        ] == [
            ("early", "早班", "00:00", "08:00", 1),
            ("middle", "中班", "08:00", "16:00", 2),
            ("night", "晚班", "16:00", "24:00", 3),
        ]

    def test_default_shifts_are_initialized_per_room(self, api_client: TestClient, db_session) -> None:
        user_id, token = _create_admin(api_client, db_session)
        second_room = OrgUnit(code="room-2", name="第二机房", type="room")
        db_session.add(second_room)
        db_session.add(SysDataScope(user_id=user_id, scope_type="all"))
        db_session.commit()

        first_room_id = db_session.scalar(select(OrgUnit.id).where(OrgUnit.code == "room-1"))
        assert first_room_id is not None
        api_client.headers["X-Current-Room-Id"] = str(first_room_id)
        first = api_client.get("/api/v1/shifts", headers={"Authorization": f"Bearer {token}"})
        api_client.headers["X-Current-Room-Id"] = str(second_room.id)
        second = api_client.get(
            "/api/v1/shifts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert len(first.json()["data"]) == 3
        assert len(second.json()["data"]) == 3
        assert {shift["org_unit_id"] for shift in first.json()["data"]} != {
            shift["org_unit_id"] for shift in second.json()["data"]
        }

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

    def test_rejects_overlap_with_overnight_shift_after_midnight(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/shifts",
            json={"code": "overnight", "name": "跨夜班", "start_time": "20:00", "end_time": "04:00"},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = api_client.post(
            "/api/v1/shifts",
            json={"code": "after_midnight", "name": "凌晨班", "start_time": "02:00", "end_time": "06:00"},
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
        room = OrgUnit(code="room-1", name="测试机房", type="room")
        db_session.add(room)
        db_session.flush()
        sd = ShiftDef(org_unit_id=room.id, code="early", name="早班", start_time="00:00", end_time="08:00")
        db_session.add(sd)
        db_session.commit()

        assert sd.status == "enabled"
        assert sd.display_order == 0

    def test_unique_code(self, db_session) -> None:
        room = OrgUnit(code="room-1", name="测试机房", type="room")
        db_session.add(room)
        db_session.flush()
        db_session.add(ShiftDef(org_unit_id=room.id, code="early", name="早班", start_time="00:00", end_time="08:00"))
        db_session.commit()
        db_session.add(ShiftDef(org_unit_id=room.id, code="early", name="早班重复", start_time="10:00", end_time="14:00"))
        with pytest.raises(Exception):
            db_session.commit()
