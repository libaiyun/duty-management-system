import pytest
from fastapi.testclient import TestClient

from app.models.organization import OrgUnit
from app.models.shift import ShiftRule, ShiftRuleItem
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


def _broadcast_items() -> list[dict]:
    return [
        {"group_type": "night_early_group", "sequence_no": 1, "shift_code": "night", "repeat_count": 1},
        {"group_type": "night_early_group", "sequence_no": 2, "shift_code": "early", "repeat_count": 1},
        {"group_type": "night_early_group", "sequence_no": 3, "shift_code": "night", "repeat_count": 1},
        {"group_type": "night_early_group", "sequence_no": 4, "shift_code": "early", "repeat_count": 1},
        {"group_type": "night_early_group", "sequence_no": 5, "shift_code": "rest", "repeat_count": 2},
        {"group_type": "middle_group", "sequence_no": 1, "shift_code": "middle", "repeat_count": 2},
        {"group_type": "middle_group", "sequence_no": 2, "shift_code": "rest", "repeat_count": 2},
    ]


class TestShiftRuleApi:
    def test_list_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/shift-rules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create_rule_with_items(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "broadcast_main",
                "name": "广播发射台主城区规则",
                "station_type": "station_broadcast",
                "persons_per_shift": 2,
                "rule_type": "broadcast_fixed",
                "items": _broadcast_items(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "broadcast_main"
        assert data["persons_per_shift"] == 2
        assert data["status"] == "draft"
        assert len(data["items"]) == 7
        assert data["items"][0]["shift_code"] == "night"

    def test_create_rule_without_items(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={"code": "simple", "name": "简单规则", "station_type": "station_broadcast"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["persons_per_shift"] == 2

    def test_create_rule_with_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        unit = OrgUnit(code="ROOM1", name="一号机房", type="room")
        db_session.add(unit)
        db_session.commit()
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "with_org",
                "name": "机房规则",
                "station_type": "station_broadcast",
                "org_unit_id": unit.id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["org_unit_id"] == unit.id

    def test_create_rule_org_unit_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "bad_org",
                "name": "规则",
                "station_type": "station_broadcast",
                "org_unit_id": 99999,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_get_rule_detail(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "detail",
                "name": "详情规则",
                "station_type": "station_broadcast",
                "items": _broadcast_items(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]
        resp = api_client.get(
            f"/api/v1/shift-rules/{rule_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "详情规则"
        assert len(resp.json()["data"]["items"]) == 7

    def test_update_rule_fields(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={"code": "upd", "name": "原名", "station_type": "station_broadcast"},
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]
        resp = api_client.put(
            f"/api/v1/shift-rules/{rule_id}",
            json={"name": "新名", "status": "enabled", "persons_per_shift": 3},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "新名"
        assert data["status"] == "enabled"
        assert data["persons_per_shift"] == 3

    def test_update_rule_replaces_items(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "items_upd",
                "name": "规则",
                "station_type": "station_broadcast",
                "items": _broadcast_items(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]
        resp = api_client.put(
            f"/api/v1/shift-rules/{rule_id}",
            json={"items": [
                {"group_type": "middle_group", "sequence_no": 1, "shift_code": "middle", "repeat_count": 1},
            ]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["items"][0]["shift_code"] == "middle"

    def test_update_rule_omit_items_keeps_them(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "keep_items",
                "name": "规则",
                "station_type": "station_broadcast",
                "items": _broadcast_items(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]
        resp = api_client.put(
            f"/api/v1/shift-rules/{rule_id}",
            json={"name": "只改名"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 7

    def test_delete_rule(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={"code": "del", "name": "待删除", "station_type": "station_broadcast"},
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]
        resp = api_client.delete(
            f"/api/v1/shift-rules/{rule_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        resp = api_client.get(
            f"/api/v1/shift-rules/{rule_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404

    def test_rule_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get(
            "/api/v1/shift-rules/99999", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 404

    def test_duplicate_code(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/shift-rules",
            json={"code": "dup", "name": "规则A", "station_type": "station_broadcast"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={"code": "dup", "name": "规则B", "station_type": "station_broadcast"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_persons_per_shift_min(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "zero",
                "name": "规则",
                "station_type": "station_broadcast",
                "persons_per_shift": 0,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_create_items_sorted_by_sequence(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "sorted",
                "name": "乱序明细",
                "station_type": "station_broadcast",
                "items": [
                    {"group_type": "g", "sequence_no": 3, "shift_code": "night"},
                    {"group_type": "g", "sequence_no": 1, "shift_code": "early"},
                    {"group_type": "g", "sequence_no": 2, "shift_code": "middle"},
                ],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        create_seqs = [i["sequence_no"] for i in resp.json()["data"]["items"]]
        assert create_seqs == [1, 2, 3]
        rule_id = resp.json()["data"]["id"]
        resp = api_client.get(
            f"/api/v1/shift-rules/{rule_id}", headers={"Authorization": f"Bearer {token}"}
        )
        get_seqs = [i["sequence_no"] for i in resp.json()["data"]["items"]]
        assert get_seqs == create_seqs

    def test_requires_permission(self, api_client: TestClient, db_session) -> None:
        create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")
        resp = api_client.get("/api/v1/shift-rules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestShiftRuleModel:
    def test_default_values(self, db_session) -> None:
        rule = ShiftRule(code="r1", name="规则", station_type="station_broadcast")
        db_session.add(rule)
        db_session.commit()
        assert rule.status == "draft"
        assert rule.persons_per_shift == 2
        assert rule.rule_type == "broadcast_fixed"

    def test_cascade_delete_items(self, db_session) -> None:
        rule = ShiftRule(code="r2", name="规则", station_type="station_broadcast")
        rule.items.append(ShiftRuleItem(group_type="middle_group", sequence_no=1, shift_code="middle"))
        db_session.add(rule)
        db_session.commit()
        rule_id = rule.id
        db_session.delete(rule)
        db_session.commit()
        remaining = db_session.query(ShiftRuleItem).filter(ShiftRuleItem.rule_id == rule_id).all()
        assert remaining == []

    def test_unique_code(self, db_session) -> None:
        db_session.add(ShiftRule(code="uni", name="规则A", station_type="station_broadcast"))
        db_session.commit()
        db_session.add(ShiftRule(code="uni", name="规则B", station_type="station_broadcast"))
        with pytest.raises(Exception):
            db_session.commit()
