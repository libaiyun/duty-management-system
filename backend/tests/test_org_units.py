import pytest
from fastapi.testclient import TestClient

from app.models.organization import OrgUnit
from app.models.user import SysDataScope, SysPermission, SysRole
from app.services.auth import create_user

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session) -> tuple[int, str]:
    user = create_user(db_session, "admin", "password123", "管理员")
    perm = SysPermission(code="org:unit:view", name="View Org", type="api")
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.append(perm)
    db_session.add_all([perm, role])
    user.roles.append(role)
    db_session.flush()
    db_session.add(SysDataScope(user_id=user.id, scope_type="all", org_unit_id=None))
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    return user.id, token


class TestOrgUnitApi:
    def test_get_org_units_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/org-units", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "station-1", "name": "广播发射台", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "station-1"
        assert data["name"] == "广播发射台"
        assert data["type"] == "station"
        assert data["status"] == "enabled"

    def test_create_child_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        parent_resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "station-1", "name": "广播发射台", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        parent_id = parent_resp.json()["data"]["id"]

        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "room-1", "name": "机房A", "type": "room", "parent_id": parent_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["parent_id"] == parent_id

    def test_get_org_tree(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/org-units",
            json={"code": "station-1", "name": "台站", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        api_client.post(
            "/api/v1/org-units",
            json={"code": "room-1", "name": "机房A", "type": "room", "parent_id": 1},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = api_client.get("/api/v1/org-units/tree", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        tree = resp.json()["data"]
        assert len(tree) == 1
        assert tree[0]["name"] == "台站"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["name"] == "机房A"

    def test_update_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "station-1", "name": "广播发射台", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        unit_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/org-units/{unit_id}",
            json={"name": "更新后的台站", "status": "disabled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "更新后的台站"
        assert data["status"] == "disabled"

    def test_delete_org_unit_without_children(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "station-1", "name": "台站", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        unit_id = resp.json()["data"]["id"]

        resp = api_client.delete(
            f"/api/v1/org-units/{unit_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        resp = api_client.get("/api/v1/org-units", headers={"Authorization": f"Bearer {token}"})
        assert len(resp.json()["data"]) == 0

    def test_delete_org_unit_with_children_blocked(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/org-units",
            json={"code": "station-1", "name": "台站", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        api_client.post(
            "/api/v1/org-units",
            json={"code": "room-1", "name": "机房", "type": "room", "parent_id": 1},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = api_client.delete(
            "/api/v1/org-units/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "STATE_CONFLICT"

    def test_org_units_requires_permission(self, api_client: TestClient, db_session) -> None:
        user = create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")

        resp = api_client.get("/api/v1/org-units", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_create_duplicate_code_returns_409(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/org-units",
            json={"code": "dup", "name": "台站A", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "dup", "name": "台站B", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "STATE_CONFLICT"

    def test_create_with_invalid_parent_returns_404(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "orphan", "name": "机房", "type": "room", "parent_id": 99999},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_delete_blocked_when_has_person(self, api_client: TestClient, db_session) -> None:
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "room-with-person", "name": "机房", "type": "room"},
            headers={"Authorization": f"Bearer {token}"},
        )
        unit_id = resp.json()["data"]["id"]
        db_session.add(Person(code="P900", name="张三", person_type="duty_operator", org_unit_id=unit_id))
        db_session.commit()

        resp = api_client.delete(
            f"/api/v1/org-units/{unit_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "STATE_CONFLICT"

    def test_disable_blocked_when_has_active_person(self, api_client: TestClient, db_session) -> None:
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "room-active", "name": "机房", "type": "room"},
            headers={"Authorization": f"Bearer {token}"},
        )
        unit_id = resp.json()["data"]["id"]
        db_session.add(Person(code="P901", name="李四", person_type="duty_operator", org_unit_id=unit_id))
        db_session.commit()

        resp = api_client.put(
            f"/api/v1/org-units/{unit_id}",
            json={"status": "disabled"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "STATE_CONFLICT"

    def test_update_self_parent_blocked(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "self-ref", "name": "台站", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        )
        unit_id = resp.json()["data"]["id"]
        resp = api_client.put(
            f"/api/v1/org-units/{unit_id}",
            json={"parent_id": unit_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409


class TestOrgUnitManager:
    def test_create_with_manager(self, api_client: TestClient, db_session) -> None:
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        person = Person(code="MGR1", name="主任", person_type="director")
        db_session.add(person)
        db_session.commit()

        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "st-mgr", "name": "台站", "type": "station", "manager_person_id": person.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["manager_person_id"] == person.id

    def test_create_with_invalid_manager_returns_404(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/org-units",
            json={"code": "st-badmgr", "name": "台站", "type": "station", "manager_person_id": 99999},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_update_manager_bind_and_unbind(self, api_client: TestClient, db_session) -> None:
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        person = Person(code="MGR2", name="副主任", person_type="deputy")
        db_session.add(person)
        db_session.commit()
        unit_id = api_client.post(
            "/api/v1/org-units",
            json={"code": "st-upd-mgr", "name": "台站", "type": "station"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/org-units/{unit_id}",
            json={"manager_person_id": person.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["manager_person_id"] == person.id

        resp = api_client.put(
            f"/api/v1/org-units/{unit_id}",
            json={"manager_person_id": None},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["manager_person_id"] is None

    def test_update_without_manager_field_keeps_value(self, api_client: TestClient, db_session) -> None:
        from app.models.person import Person

        _, token = _create_admin(api_client, db_session)
        person = Person(code="MGR3", name="主任3", person_type="director")
        db_session.add(person)
        db_session.commit()
        unit_id = api_client.post(
            "/api/v1/org-units",
            json={
                "code": "st-keep-mgr", "name": "台站", "type": "station",
                "manager_person_id": person.id,
            },
            headers={"Authorization": f"Bearer {token}"},
        ).json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/org-units/{unit_id}",
            json={"name": "台站改名"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["manager_person_id"] == person.id


class TestOrgUnitDataScope:
    def _create_scoped_user(
        self, api_client: TestClient, db_session, username: str, scope_org_id: int,
    ) -> str:
        user = create_user(db_session, username, "pass123", username)
        perm = db_session.query(SysPermission).filter(SysPermission.code == "org:unit:view").first()
        if perm is None:
            perm = SysPermission(code="org:unit:view", name="View Org", type="api")
            db_session.add(perm)
        role = SysRole(code=f"role-{username}", name=username)
        role.permissions.append(perm)
        db_session.add(role)
        user.roles.append(role)
        db_session.flush()
        db_session.add(SysDataScope(user_id=user.id, scope_type="room", org_unit_id=scope_org_id))
        db_session.commit()
        return _login(api_client, db_session, username, "pass123")

    def test_room_scope_filters_org_units(self, api_client: TestClient, db_session) -> None:
        _, admin_token = _create_admin(api_client, db_session)
        r1 = api_client.post(
            "/api/v1/org-units",
            json={"code": "room-1", "name": "机房1", "type": "room"},
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()["data"]["id"]
        api_client.post(
            "/api/v1/org-units",
            json={"code": "room-2", "name": "机房2", "type": "room"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        token = self._create_scoped_user(api_client, db_session, "scoped", r1)
        resp = api_client.get("/api/v1/org-units", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == r1

    def test_no_scope_returns_empty(self, api_client: TestClient, db_session) -> None:
        _, admin_token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/org-units",
            json={"code": "room-x", "name": "机房", "type": "room"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 有权限但无数据范围
        user = create_user(db_session, "noscope", "pass123", "无范围")
        perm = db_session.query(SysPermission).filter(SysPermission.code == "org:unit:view").first()
        role = SysRole(code="role-noscope", name="noscope")
        role.permissions.append(perm)
        db_session.add(role)
        user.roles.append(role)
        db_session.commit()
        token = _login(api_client, db_session, "noscope", "pass123")

        resp = api_client.get("/api/v1/org-units", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestOrgUnitModel:
    def test_org_unit_default_values(self, db_session) -> None:
        unit = OrgUnit(code="s1", name="台站", type="station")
        db_session.add(unit)
        db_session.commit()

        assert unit.status == "enabled"
        assert unit.sort_order == 0
        assert unit.parent_id is None

    def test_org_unit_unique_code(self, db_session) -> None:
        db_session.add(OrgUnit(code="s1", name="台站1", type="station"))
        db_session.commit()
        db_session.add(OrgUnit(code="s1", name="台站2", type="station"))
        with pytest.raises(Exception):
            db_session.commit()

    def test_org_unit_tree_self_reference(self, db_session) -> None:
        parent = OrgUnit(code="station", name="台站", type="station")
        child = OrgUnit(code="room", name="机房", type="room", parent=parent)
        db_session.add_all([parent, child])
        db_session.commit()

        assert child.parent_id == parent.id
