import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.user import SysDataScope, SysPermission, SysRole
from app.services.auth import create_user

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session, select_room: bool = True) -> tuple[int, str]:
    room = db_session.scalars(select(OrgUnit).where(OrgUnit.type == "room")).first()
    if room is None:
        room = OrgUnit(code="admin-current-room", name="管理员当前机房", type="room")
        db_session.add(room)
        db_session.flush()
    user = create_user(db_session, "admin", "password123", "管理员")
    perm = SysPermission(code="person:manage:view", name="View Person", type="api")
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.append(perm)
    db_session.add_all([perm, role])
    user.roles.append(role)
    db_session.flush()
    db_session.add(SysDataScope(user_id=user.id, scope_type="all", org_unit_id=None))
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    if select_room:
        api_client.headers["X-Current-Room-Id"] = str(room.id)
    else:
        api_client.headers.pop("X-Current-Room-Id", None)
    return user.id, token


class TestPersonApi:
    def test_get_persons_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/persons", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create_person(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/persons",
            json={"code": "P001", "name": "张三", "person_type": "duty_operator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "P001"
        assert data["name"] == "张三"
        assert data["person_type"] == "duty_operator"
        assert data["status"] == "enabled"
        assert data["participate_schedule"] is False

    def test_create_person_without_code_generates_unique_code(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        headers = {"Authorization": f"Bearer {token}"}

        first = api_client.post("/api/v1/persons", json={"name": "甲", "person_type": "duty_operator"}, headers=headers)
        second = api_client.post("/api/v1/persons", json={"name": "乙", "person_type": "duty_operator"}, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["code"]
        assert first.json()["data"]["code"] != second.json()["data"]["code"]

    def test_create_person_with_schedule(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/persons",
            json={
                "code": "P002", "name": "李四", "person_type": "duty_operator",
                "participate_schedule": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["participate_schedule"] is True

    def test_get_person_detail(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/persons",
            json={"code": "P003", "name": "王五", "person_type": "duty_operator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        person_id = resp.json()["data"]["id"]

        resp = api_client.get(
            f"/api/v1/persons/{person_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "王五"

    def test_person_response_includes_account_binding_status(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        person = Person(code="BOUND", name="已绑定人员", person_type="duty_operator", org_unit_id=1)
        db_session.add(person)
        db_session.flush()
        create_user(db_session, "bound-account", "password123", "已绑定账号", person_id=person.id)
        db_session.commit()

        resp = api_client.get("/api/v1/persons", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        binding = next(item for item in resp.json()["data"] if item["id"] == person.id)
        assert binding["account_bound"] is True
        assert binding["account_username"] == "bound-account"

    def test_update_person(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/persons",
            json={"code": "P004", "name": "赵六", "person_type": "duty_operator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        person_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/persons/{person_id}",
            json={"name": "赵六(改)", "status": "disabled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "赵六(改)"
        assert data["status"] == "disabled"

    def test_persons_requires_permission(self, api_client: TestClient, db_session) -> None:
        user = create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")

        resp = api_client.get("/api/v1/persons", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_create_person_invalid_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/persons",
            json={"code": "P010", "name": "Invalid", "person_type": "duty_operator", "org_unit_id": 99999},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["org_unit_id"] is not None

    def test_create_duplicate_code_returns_409(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/persons",
            json={"code": "P100", "name": "甲", "person_type": "duty_operator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/persons",
            json={"code": "P100", "name": "乙", "person_type": "duty_operator"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "STATE_CONFLICT"


class TestPersonDataScope:
    def test_room_scope_filters_persons(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit

        _, admin_token = _create_admin(api_client, db_session)
        room1 = OrgUnit(code="room-a", name="机房A", type="room")
        room2 = OrgUnit(code="room-b", name="机房B", type="room")
        db_session.add_all([room1, room2])
        db_session.flush()
        person_a = Person(code="PA1", name="甲", person_type="duty_operator", org_unit_id=room1.id)
        person_b = Person(code="PB1", name="乙", person_type="duty_operator", org_unit_id=room2.id)
        db_session.add_all([person_a, person_b])
        db_session.flush()

        scoped = create_user(db_session, "scoped", "pass123", "范围用户", person_id=person_a.id)
        perm = db_session.query(SysPermission).filter(
            SysPermission.code == "person:manage:view"
        ).first()
        role = SysRole(code="role-scoped", name="scoped")
        role.permissions.append(perm)
        db_session.add(role)
        scoped.roles.append(role)
        db_session.flush()
        db_session.add(SysDataScope(user_id=scoped.id, scope_type="room", org_unit_id=room1.id))
        db_session.commit()

        token = _login(api_client, db_session, "scoped", "pass123")
        resp = api_client.get("/api/v1/persons", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["code"] == "PA1"


class TestPersonCurrentRoom:
    def test_admin_requires_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session, select_room=False)

        resp = api_client.get("/api/v1/persons", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 422
        assert resp.json()["code"] == "ADMIN_NO_ROOM_SELECTED"

    def test_create_assigns_current_room_despite_client_org_unit(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit

        _, token = _create_admin(api_client, db_session)
        room_a = OrgUnit(code="current-person-a", name="机房A", type="room")
        room_b = OrgUnit(code="current-person-b", name="机房B", type="room")
        db_session.add_all([room_a, room_b])
        db_session.commit()

        resp = api_client.post(
            "/api/v1/persons",
            json={"code": "CURRENT-PERSON", "name": "当前机房人员", "person_type": "duty_operator", "org_unit_id": room_b.id},
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)},
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["org_unit_id"] == room_a.id

    def test_detail_rejects_person_outside_current_room(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit

        _, token = _create_admin(api_client, db_session)
        room_a = OrgUnit(code="person-detail-a", name="机房A", type="room")
        room_b = OrgUnit(code="person-detail-b", name="机房B", type="room")
        db_session.add_all([room_a, room_b])
        db_session.flush()
        person = Person(code="OUTSIDE-PERSON", name="其他机房人员", person_type="duty_operator", org_unit_id=room_b.id)
        db_session.add(person)
        db_session.commit()

        resp = api_client.get(
            f"/api/v1/persons/{person.id}",
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)},
        )

        assert resp.status_code == 404

    def test_regular_user_uses_bound_person_room(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit

        room_a = OrgUnit(code="bound-person-a", name="机房A", type="room")
        room_b = OrgUnit(code="bound-person-b", name="机房B", type="room")
        db_session.add_all([room_a, room_b])
        db_session.flush()
        bound_person = Person(code="BOUND-PERSON", name="绑定人员", person_type="duty_operator", org_unit_id=room_a.id)
        other_person = Person(code="OTHER-PERSON", name="其他人员", person_type="duty_operator", org_unit_id=room_b.id)
        db_session.add_all([bound_person, other_person])
        db_session.flush()
        user = create_user(db_session, "bound-user", "password123", "绑定用户", person_id=bound_person.id)
        permission = SysPermission(code="person:manage:view", name="View Person", type="api")
        role = SysRole(code="bound-person-role", name="Bound Person Role")
        role.permissions.append(permission)
        db_session.add_all([permission, role])
        user.roles.append(role)
        db_session.commit()
        token = _login(api_client, db_session, "bound-user", "password123")

        resp = api_client.get(
            "/api/v1/persons",
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_b.id)},
        )

        assert resp.status_code == 200
        assert [person["id"] for person in resp.json()["data"]] == [bound_person.id]


class TestPersonModel:
    def test_person_default_values(self, db_session) -> None:
        p = Person(code="P001", name="测试", person_type="duty_operator")
        db_session.add(p)
        db_session.commit()

        assert p.status == "enabled"
        assert p.participate_schedule is False
        assert p.org_unit_id is None

    def test_person_unique_code(self, db_session) -> None:
        db_session.add(Person(code="P001", name="A", person_type="duty_operator"))
        db_session.commit()
        db_session.add(Person(code="P001", name="B", person_type="duty_operator"))
        with pytest.raises(Exception):
            db_session.commit()
