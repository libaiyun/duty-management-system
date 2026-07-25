import pytest
from app.core.permissions import BUILTIN_ROLES
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user, seed_permission_system
from fastapi.testclient import TestClient

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

    def test_create_user_with_duplicate_username_returns_conflict(
        self, api_client: TestClient, db_session,
    ) -> None:
        _, token = _create_admin(api_client, db_session)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"username": "duplicate-user", "password": "pass123", "display_name": "用户"}
        assert api_client.post("/api/v1/users", json=payload, headers=headers).status_code == 200

        resp = api_client.post("/api/v1/users", json=payload, headers=headers)

        assert resp.status_code == 409
        assert resp.json()["code"] == "STATE_CONFLICT"

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

    def test_update_user_rejects_unknown_status(self, api_client: TestClient, db_session) -> None:
        user_id, token = _create_admin(api_client, db_session)

        resp = api_client.put(
            f"/api/v1/users/{user_id}",
            json={"status": "unexpected"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_assign_user_roles(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        seed_permission_system(db_session)
        role = db_session.query(SysRole).filter_by(code="schedule_admin").one()

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
        create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")

        resp = api_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_binding_persons_lists_all_rooms_without_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room_a = OrgUnit(code="binding-room-a", name="绑定机房A", type="room")
        room_b = OrgUnit(code="binding-room-b", name="绑定机房B", type="room")
        db_session.add_all([room_a, room_b])
        db_session.flush()
        db_session.add_all([
            Person(code="BIND-A", name="甲", person_type="duty_operator", org_unit_id=room_a.id),
            Person(code="BIND-B", name="乙", person_type="duty_operator", org_unit_id=room_b.id),
        ])
        db_session.commit()

        resp = api_client.get("/api/v1/users/persons", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        assert {person["code"] for person in resp.json()["data"]} == {"BIND-A", "BIND-B"}

    def test_binding_persons_requires_system_user_permission(self, api_client: TestClient, db_session) -> None:
        user = create_user(db_session, "person-manager", "password123", "人员管理员")
        permission = SysPermission(code="person:manage:view", name="View Person", type="api")
        role = SysRole(code="person-manager-role", name="Person Manager")
        role.permissions.append(permission)
        db_session.add_all([permission, role])
        user.roles.append(role)
        db_session.commit()
        token = _login(api_client, db_session, "person-manager", "password123")

        resp = api_client.get("/api/v1/users/persons", headers={"Authorization": f"Bearer {token}"})

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
        assert resp.json()["data"]["code"] == "viewer"

    def test_list_roles(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        seed_permission_system(db_session)

        resp = api_client.get("/api/v1/roles", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert set(BUILTIN_ROLES) <= {role["code"] for role in resp.json()["data"]}

    def test_get_permissions(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)

        resp = api_client.get("/api/v1/permissions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_update_role_rejects_unknown_status(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        role = SysRole(code="status-boundary-role", name="状态边界")
        db_session.add(role)
        db_session.commit()

        resp = api_client.put(
            f"/api/v1/roles/{role.id}",
            json={"status": "unexpected"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"


class TestUserPersonBinding:
    def test_create_user_with_person(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        org = OrgUnit(code="bind-org", name="测试组织", type="station")
        person = Person(code="BIND1", name="绑定人员", person_type="duty_operator", org_unit=org)
        db_session.add_all([org, person])
        db_session.commit()

        resp = api_client.post(
            "/api/v1/users",
            json={"username": "bind1", "password": "pass", "display_name": "绑定用户", "person_id": person.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["person_id"] == person.id

    def test_create_user_with_invalid_person_returns_404(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)

        resp = api_client.post(
            "/api/v1/users",
            json={"username": "badbind", "password": "pass", "display_name": "坏绑定", "person_id": 99999},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_create_user_person_already_bound_returns_409(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        org = OrgUnit(code="dup-org", name="重复组织", type="station")
        person = Person(code="DUP1", name="已绑人员", person_type="duty_operator", org_unit=org)
        db_session.add_all([org, person])
        db_session.commit()
        api_client.post(
            "/api/v1/users",
            json={"username": "first", "password": "pass", "display_name": "第一个", "person_id": person.id},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = api_client.post(
            "/api/v1/users",
            json={"username": "second", "password": "pass", "display_name": "第二个", "person_id": person.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_update_user_bind_person(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        org = OrgUnit(code="upd-org", name="更新组织", type="station")
        person = Person(code="UPB1", name="更新绑定", person_type="duty_operator", org_unit=org)
        db_session.add_all([org, person])
        db_session.commit()
        resp = api_client.post(
            "/api/v1/users",
            json={"username": "upd1", "password": "pass", "display_name": "更新用户"},
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/users/{user_id}",
            json={"person_id": person.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["person_id"] == person.id

    def test_update_user_unbind_person(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        org = OrgUnit(code="unb-org", name="解绑组织", type="station")
        person = Person(code="UNB1", name="解绑人员", person_type="duty_operator", org_unit=org)
        db_session.add_all([org, person])
        db_session.commit()
        resp = api_client.post(
            "/api/v1/users",
            json={"username": "unb1", "password": "pass", "display_name": "解绑用户", "person_id": person.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        user_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/users/{user_id}",
            json={"person_id": None},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["person_id"] is None
