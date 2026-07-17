from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import MonthlySchedule
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleItem, ShiftRuleVersion
from app.models.user import SysDataScope, SysPermission, SysRole
from app.services.auth import create_shift_rule, create_user, publish_shift_rule, update_shift_rule

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session, select_room: bool = True, with_shift_def: bool = True) -> tuple[int, str]:
    room = db_session.scalars(select(OrgUnit).where(OrgUnit.type == "room")).first()
    if room is None:
        room = OrgUnit(code="admin-current-room", name="管理员当前机房", type="room")
        db_session.add(room)
        db_session.flush()
    user = create_user(db_session, "admin", "password123", "管理员")
    permissions = [
        SysPermission(code="shift:rule:view", name="View Shift Rule", type="api"),
        SysPermission(code="shift:rule:manage", name="Manage Shift Rule", type="api"),
    ]
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.extend(permissions)
    db_session.add_all([*permissions, role])
    user.roles.append(role)
    db_session.flush()
    db_session.add(SysDataScope(user_id=user.id, scope_type="all", org_unit_id=None))
    if with_shift_def and not db_session.scalar(select(ShiftDef).where(ShiftDef.org_unit_id == room.id)):
        db_session.add(ShiftDef(
            org_unit_id=room.id, code="default_shift", name="默认班次",
            start_time="08:00", end_time="16:00",
        ))
        db_session.add_all([
            Person(code="default_operator_1", name="默认值班员1", org_unit_id=room.id,
                   participate_schedule=True, person_type="duty_operator"),
            Person(code="default_operator_2", name="默认值班员2", org_unit_id=room.id,
                   participate_schedule=True, person_type="duty_operator"),
        ])
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    if select_room:
        api_client.headers["X-Current-Room-Id"] = str(room.id)
    else:
        api_client.headers.pop("X-Current-Room-Id", None)
    return user.id, token


def _sample_days(cycle_days: int = 6) -> list[dict]:
    days = []
    for day_no in range(1, cycle_days + 1):
        days.append({"day_no": day_no, "cells": [{"shift_def_id": 1, "person_ids": [1, 2]}]})
    return days


def _create_org(db_session) -> OrgUnit:
    org = OrgUnit(code="ORG1", name="测试机房", type="room")
    db_session.add(org)
    db_session.commit()
    return org


class TestShiftRuleApi:
    def test_list_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session, with_shift_def=False)
        resp = api_client.get("/api/v1/shift-rules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create_rule_with_days(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        future_start = (date.today() + timedelta(days=10)).isoformat()
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_01",
                "name": "广播发射台规则",
                "cycle_days": 6,
                "start_date": future_start,
                "persons_per_cell": 2,
                "days": _sample_days(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "rule_01"
        assert data["cycle_days"] == 6
        assert data["start_date"] == future_start
        assert data["persons_per_cell"] == 2
        assert data["status"] == "draft"
        assert len(data["items"]) == 6

    def test_create_rule_without_days(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_02",
                "name": "空规则",
                "cycle_days": 3,
                "start_date": "2026-08-01",
                "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "rule_02"
        assert len(data["items"]) == 0

    def test_create_rule_without_code_generates_unique_code(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"name": "空规则", "cycle_days": 3, "start_date": "2027-08-01", "persons_per_cell": 1}

        first = api_client.post("/api/v1/shift-rules", json=payload, headers=headers)
        second = api_client.post("/api/v1/shift-rules", json={**payload, "name": "空规则2"}, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["code"]
        assert first.json()["data"]["code"] != second.json()["data"]["code"]

    def test_create_rule_with_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_03",
                "name": "有机房规则",
                "cycle_days": 5,
                "start_date": "2026-09-01",
                "persons_per_cell": 1,
                "org_unit_id": 99999,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["org_unit_id"] is not None

    def test_create_rule_org_unit_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_04",
                "name": "无效机房",
                "cycle_days": 3,
                "start_date": "2026-08-01",
                "persons_per_cell": 1,
                "org_unit_id": 99999,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_get_rule_detail(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_05",
                "name": "详情规则",
                "cycle_days": 7,
                "start_date": "2026-10-01",
                "persons_per_cell": 2,
                "days": _sample_days(cycle_days=7),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]

        resp = api_client.get(f"/api/v1/shift-rules/{rule_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "详情规则"
        assert len(resp.json()["data"]["items"]) == 7

    def test_update_rule_fields(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_06",
                "name": "旧名称",
                "cycle_days": 4,
                "start_date": "2026-11-01",
                "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/shift-rules/{rule_id}",
            json={"name": "新名称", "persons_per_cell": 3},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "新名称"
        assert data["persons_per_cell"] == 3

    def test_update_with_days_creates_new_version(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_07",
                "name": "版本测试",
                "cycle_days": 3,
                "start_date": "2026-12-01",
                "persons_per_cell": 2,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]

        resp = api_client.put(
            f"/api/v1/shift-rules/{rule_id}",
            json={"name": "版本测试v2", "days": _sample_days()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 6

    def test_delete_rule(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_08",
                "name": "待删除",
                "cycle_days": 3,
                "start_date": "2027-01-01",
                "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]

        resp = api_client.delete(f"/api/v1/shift-rules/{rule_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_rule_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/shift-rules/99999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_duplicate_code(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "dup_code", "name": "规则A",
                "cycle_days": 3, "start_date": "2026-12-15", "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "dup_code", "name": "规则B",
                "cycle_days": 3, "start_date": "2026-12-15", "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    def test_publish_rule(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        future_start = (date.today() + timedelta(days=10)).isoformat()
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_pub",
                "name": "可发布规则",
                "cycle_days": 6,
                "start_date": future_start,
                "persons_per_cell": 2,
                "days": _sample_days(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]

        resp = api_client.post(
            f"/api/v1/shift-rules/{rule_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "published"

    def test_publishing_another_rule_supersedes_previous_rule_and_updates_schedule(
        self, api_client: TestClient, db_session,
    ) -> None:
        _, token = _create_admin(api_client, db_session)
        first_start = (date.today() + timedelta(days=10)).isoformat()
        second_start = (date.today() + timedelta(days=20)).isoformat()

        first = api_client.post("/api/v1/shift-rules", json={
            "code": "first_active_rule", "name": "原生效规则", "cycle_days": 1,
            "start_date": first_start, "persons_per_cell": 2, "days": _sample_days(1),
        }, headers={"Authorization": f"Bearer {token}"})
        first_id = first.json()["data"]["id"]
        assert api_client.post(
            f"/api/v1/shift-rules/{first_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code == 200

        second = api_client.post("/api/v1/shift-rules", json={
            "code": "second_active_rule", "name": "新生效规则", "cycle_days": 1,
            "start_date": second_start, "persons_per_cell": 2, "days": _sample_days(1),
        }, headers={"Authorization": f"Bearer {token}"})
        second_id = second.json()["data"]["id"]
        assert api_client.post(
            f"/api/v1/shift-rules/{second_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code == 200

        first_rule = db_session.get(ShiftRule, first_id)
        second_rule = db_session.get(ShiftRule, second_id)
        first_version = db_session.scalar(select(ShiftRuleVersion).where(ShiftRuleVersion.rule_id == first_id))
        second_version = db_session.scalar(select(ShiftRuleVersion).where(ShiftRuleVersion.rule_id == second_id))
        schedule = db_session.scalar(select(MonthlySchedule))

        assert first_rule is not None and first_rule.status == "superseded"
        assert second_rule is not None and second_rule.status == "published"
        assert first_version is not None and first_version.status == "published"
        assert second_version is not None and second_version.status == "published"
        assert schedule is not None
        assert schedule.rule_id == second_id
        assert schedule.rule_version_id == second_version.id

    def test_publish_without_days_fails(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_no_days",
                "name": "无版本规则",
                "cycle_days": 3,
                "start_date": "2026-08-01",
                "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]

        resp = api_client.post(
            f"/api/v1/shift-rules/{rule_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_get_versions(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_ver",
                "name": "版本列表规则",
                "cycle_days": 4,
                "start_date": "2026-09-01",
                "persons_per_cell": 2,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        rule_id = resp.json()["data"]["id"]

        api_client.put(
            f"/api/v1/shift-rules/{rule_id}",
            json={"days": _sample_days()},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = api_client.get(
            f"/api/v1/shift-rules/{rule_id}/versions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        versions = resp.json()["data"]
        assert len(versions) >= 1

    def test_requires_permission(self, api_client: TestClient, db_session) -> None:
        resp = api_client.get("/api/v1/shift-rules")
        assert resp.status_code == 401


class TestShiftRuleCurrentRoom:
    def test_admin_requires_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session, select_room=False)

        resp = api_client.get("/api/v1/shift-rules", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 422
        assert resp.json()["code"] == "ADMIN_NO_ROOM_SELECTED"

    def test_create_assigns_current_room_despite_client_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room_a = OrgUnit(code="current-rule-a", name="机房A", type="room")
        room_b = OrgUnit(code="current-rule-b", name="机房B", type="room")
        db_session.add_all([room_a, room_b])
        db_session.flush()
        db_session.add(ShiftDef(org_unit_id=room_a.id, code="room_a_shift", name="机房A班次", start_time="08:00", end_time="16:00"))
        db_session.commit()

        resp = api_client.post(
            "/api/v1/shift-rules",
            json={"code": "current_rule", "name": "当前机房规则", "cycle_days": 1, "start_date": "2027-01-01", "persons_per_cell": 1, "org_unit_id": room_b.id},
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)},
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["org_unit_id"] == room_a.id

    def test_detail_rejects_rule_outside_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room_a = OrgUnit(code="rule-detail-a", name="机房A", type="room")
        room_b = OrgUnit(code="rule-detail-b", name="机房B", type="room")
        db_session.add_all([room_a, room_b])
        db_session.flush()
        rule = ShiftRule(code="outside_rule", name="其他机房规则", cycle_days=1, start_date="2027-01-01", persons_per_cell=1, org_unit_id=room_b.id)
        db_session.add(rule)
        db_session.commit()

        resp = api_client.get(
            f"/api/v1/shift-rules/{rule.id}",
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)},
        )

        assert resp.status_code == 404

    @pytest.mark.parametrize("method,path_suffix", [
        ("put", ""),
        ("delete", ""),
        ("post", "/publish"),
        ("get", "/versions"),
    ])
    def test_mutation_and_version_routes_reject_rule_outside_current_room(
        self, api_client: TestClient, db_session, method: str, path_suffix: str,
    ) -> None:
        _, token = _create_admin(api_client, db_session)
        room_a = OrgUnit(code=f"rule-route-a-{method}-{path_suffix}", name="机房A", type="room")
        room_b = OrgUnit(code=f"rule-route-b-{method}-{path_suffix}", name="机房B", type="room")
        db_session.add_all([room_a, room_b])
        db_session.flush()
        rule = ShiftRule(code=f"outside_{method}_{len(path_suffix)}", name="其他机房规则", cycle_days=1, start_date="2027-01-01", persons_per_cell=1, org_unit_id=room_b.id)
        db_session.add(rule)
        db_session.commit()

        kwargs = {"headers": {"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)}}
        if method == "put":
            kwargs["json"] = {}
        response = getattr(api_client, method)(
            f"/api/v1/shift-rules/{rule.id}{path_suffix}", **kwargs,
        )

        assert response.status_code == 404


class TestShiftRuleModel:
    def test_default_values(self, db_session) -> None:
        rule = ShiftRule(
            code="test_default", name="测试默认", cycle_days=5,
            start_date="2026-07-01", persons_per_cell=2,
        )
        db_session.add(rule)
        db_session.commit()

        assert rule.status == "draft"
        assert rule.cycle_days == 5
        assert rule.persons_per_cell == 2

    def test_cascade_delete_items(self, db_session) -> None:
        rule = ShiftRule(
            code="test_cascade", name="测试级联", cycle_days=3,
            start_date="2026-08-01", persons_per_cell=1,
        )
        db_session.add(rule)
        db_session.commit()

        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=3,
            start_date="2026-08-01", persons_per_cell=1,
            snapshot={"days": []},
        )
        db_session.add(v)
        db_session.commit()

        item = ShiftRuleItem(
            version_id=v.id, day_no=1,
            cell_persons={"1": [101], "2": [102]},
        )
        db_session.add(item)
        db_session.commit()

        db_session.delete(rule)
        db_session.commit()

        assert db_session.get(ShiftRuleItem, item.id) is None
        assert db_session.get(ShiftRuleVersion, v.id) is None

    def test_unique_code(self, db_session) -> None:
        db_session.add(ShiftRule(
            code="uniq_code", name="A", cycle_days=3,
            start_date="2026-07-01", persons_per_cell=1,
        ))
        db_session.commit()
        db_session.add(ShiftRule(
            code="uniq_code", name="B", cycle_days=3,
            start_date="2026-07-01", persons_per_cell=1,
        ))
        with pytest.raises(Exception):
            db_session.commit()


class TestShiftRuleValidation:
    """边界与异常测试"""

    def test_start_date_in_past_rejected(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_past", "name": "过去日期",
                "cycle_days": 3, "start_date": "2020-01-01", "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_start_date_today_rejected(self, api_client: TestClient, db_session) -> None:
        from datetime import date
        _, token = _create_admin(api_client, db_session)
        today = date.today().isoformat()
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_today", "name": "今天",
                "cycle_days": 3, "start_date": today, "persons_per_cell": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_cell_person_count_wrong(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_wrong_cnt", "name": "人数不对",
                "cycle_days": 1, "start_date": "2027-01-01", "persons_per_cell": 3,
                "days": [{"day_no": 1, "cells": [{"shift_def_id": 1, "person_ids": [1, 2]}]}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_missing_days_in_cycle(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_partial", "name": "不完整",
                "cycle_days": 3, "start_date": "2027-02-01", "persons_per_cell": 1,
                "days": [
                    {"day_no": 1, "cells": [{"shift_def_id": 1, "person_ids": [1]}]},
                ],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_human_error_messages(self, api_client: TestClient, db_session) -> None:
        """异常提示文案可读性验证"""
        _, token = _create_admin(api_client, db_session)

        r = api_client.post("/api/v1/shift-rules", json={
            "code": "err1", "name": "err", "cycle_days": 1,
            "start_date": "2020-01-01", "persons_per_cell": 1,
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422
        assert "明天" in r.json()["message"] or "过去" in r.json()["message"]

        r = api_client.post("/api/v1/shift-rules", json={
            "code": "err2", "name": "err", "cycle_days": 1,
            "start_date": "2027-05-01", "persons_per_cell": 3,
            "days": [{"day_no": 1, "cells": [{"shift_def_id": 1, "person_ids": [1, 2]}]}],
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422
        assert "需要 3 人" in r.json()["message"]

    def test_create_rejects_room_without_enabled_shift_defs(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session, with_shift_def=False)

        response = api_client.post("/api/v1/shift-rules", json={
            "code": "no_shifts", "name": "无班次规则", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 1,
        }, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 422
        assert response.json()["message"] == "当前机房未配置班次定义，无法设置排班规则。"

    def test_create_rejects_nonexistent_shift_definition(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room = db_session.scalar(select(OrgUnit).where(OrgUnit.type == "room"))
        assert room is not None
        shift = db_session.scalar(select(ShiftDef).where(ShiftDef.org_unit_id == room.id))
        persons = list(db_session.scalars(select(Person).where(Person.org_unit_id == room.id)).all())
        assert shift is not None

        response = api_client.post("/api/v1/shift-rules", json={
            "code": "unknown_shift_rule", "name": "不存在班次", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 2,
            "days": [{"day_no": 1, "cells": [
                {"shift_def_id": shift.id, "person_ids": [persons[0].id, persons[1].id]},
                {"shift_def_id": 99999, "person_ids": [persons[0].id, persons[1].id]},
            ]}],
        }, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 422
        assert "不属于当前机房的启用班次" in response.json()["message"]

    def test_create_rejects_shift_definition_from_another_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room = db_session.scalar(select(OrgUnit).where(OrgUnit.type == "room"))
        assert room is not None
        shift = db_session.scalar(select(ShiftDef).where(ShiftDef.org_unit_id == room.id))
        persons = list(db_session.scalars(select(Person).where(Person.org_unit_id == room.id)).all())
        other_room = OrgUnit(code="other-rule-room", name="其他机房", type="room")
        other_shift = ShiftDef(
            org_unit=other_room, code="other_shift", name="其他班次", start_time="16:00", end_time="24:00",
        )
        db_session.add_all([other_room, other_shift])
        db_session.commit()
        assert shift is not None

        response = api_client.post("/api/v1/shift-rules", json={
            "code": "foreign_shift_rule", "name": "跨机房班次", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 2,
            "days": [{"day_no": 1, "cells": [
                {"shift_def_id": shift.id, "person_ids": [persons[0].id, persons[1].id]},
                {"shift_def_id": other_shift.id, "person_ids": [persons[0].id, persons[1].id]},
            ]}],
        }, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 422
        assert "不属于当前机房的启用班次" in response.json()["message"]

    def test_create_rejects_disabled_shift_definition(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room = db_session.scalar(select(OrgUnit).where(OrgUnit.type == "room"))
        assert room is not None
        enabled_shift = db_session.scalar(select(ShiftDef).where(ShiftDef.org_unit_id == room.id))
        disabled_shift = ShiftDef(
            org_unit_id=room.id, code="disabled_rule_shift", name="停用班次",
            start_time="16:00", end_time="24:00", status="disabled",
        )
        persons = list(db_session.scalars(select(Person).where(Person.org_unit_id == room.id)).all())
        db_session.add(disabled_shift)
        db_session.commit()
        assert enabled_shift is not None

        response = api_client.post("/api/v1/shift-rules", json={
            "code": "disabled_shift_rule", "name": "停用班次", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 2,
            "days": [{"day_no": 1, "cells": [
                {"shift_def_id": enabled_shift.id, "person_ids": [persons[0].id, persons[1].id]},
                {"shift_def_id": disabled_shift.id, "person_ids": [persons[0].id, persons[1].id]},
            ]}],
        }, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 422
        assert "不属于当前机房的启用班次" in response.json()["message"]

    def test_update_and_publish_reject_room_without_enabled_shift_defs(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        created = api_client.post("/api/v1/shift-rules", json={
            "code": "disabled_shifts_rule", "name": "禁用班次规则", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 2,
            "days": _sample_days(1),
        }, headers={"Authorization": f"Bearer {token}"})
        rule_id = created.json()["data"]["id"]
        shift = db_session.scalar(select(ShiftDef).where(ShiftDef.code == "default_shift"))
        assert shift is not None
        shift.status = "disabled"
        db_session.commit()

        updated = api_client.put(f"/api/v1/shift-rules/{rule_id}", json={"name": "不能编辑"}, headers={"Authorization": f"Bearer {token}"})
        published = api_client.post(f"/api/v1/shift-rules/{rule_id}/publish", headers={"Authorization": f"Bearer {token}"})

        assert updated.status_code == 422
        assert published.status_code == 422
        assert updated.json()["message"] == "当前机房未配置班次定义，无法设置排班规则。"
        assert published.json()["message"] == "当前机房未配置班次定义，无法设置排班规则。"

    @pytest.mark.parametrize("status,participate_schedule,person_type", [
        ("disabled", True, "duty_operator"),
        ("enabled", False, "duty_operator"),
        ("enabled", True, "maintenance"),
    ])
    def test_create_rejects_ineligible_cell_person(
        self, api_client: TestClient, db_session, status: str, participate_schedule: bool, person_type: str,
    ) -> None:
        _, token = _create_admin(api_client, db_session)
        room = db_session.scalar(select(OrgUnit).where(OrgUnit.type == "room"))
        assert room is not None
        shift = ShiftDef(org_unit_id=room.id, code="validation_shift", name="验证班", start_time="08:00", end_time="16:00")
        person = Person(code=f"validation_{status}_{str(participate_schedule).lower()}_{person_type}", name="验证人员", org_unit_id=room.id, status=status, participate_schedule=participate_schedule, person_type=person_type)
        db_session.add_all([shift, person])
        db_session.commit()

        response = api_client.post("/api/v1/shift-rules", json={
            "code": f"ineligible_{status}_{str(participate_schedule).lower()}_{person_type}", "name": "人员验证", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 1,
            "days": [{"day_no": 1, "cells": [{"shift_def_id": shift.id, "person_ids": [person.id]}]}],
        }, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 422

    def test_create_rejects_duplicate_cell_person(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room = db_session.scalar(select(OrgUnit).where(OrgUnit.type == "room"))
        assert room is not None
        shift = ShiftDef(org_unit_id=room.id, code="duplicate_shift", name="验证班", start_time="08:00", end_time="16:00")
        person = Person(code="duplicate_person", name="验证人员", org_unit_id=room.id, participate_schedule=True, person_type="duty_operator")
        db_session.add_all([shift, person])
        db_session.commit()

        response = api_client.post("/api/v1/shift-rules", json={
            "code": "duplicate_person_rule", "name": "重复人员", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 2,
            "days": [{"day_no": 1, "cells": [{"shift_def_id": shift.id, "person_ids": [person.id, person.id]}]}],
        }, headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 422

    def test_editing_published_rule_creates_draft_for_republishing(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room = db_session.scalar(select(OrgUnit).where(OrgUnit.type == "room"))
        assert room is not None
        shift = ShiftDef(org_unit_id=room.id, code="republish_shift", name="验证班", start_time="08:00", end_time="16:00")
        person = Person(code="republish_person", name="验证人员", org_unit_id=room.id, participate_schedule=True, person_type="duty_operator")
        db_session.add_all([shift, person])
        db_session.commit()
        payload = {
            "code": "republish_rule", "name": "重新发布规则", "cycle_days": 1,
            "start_date": "2027-01-01", "persons_per_cell": 1,
            "days": [{"day_no": 1, "cells": [
                {"shift_def_id": 1, "person_ids": [1]},
                {"shift_def_id": shift.id, "person_ids": [person.id]},
            ]}],
        }
        created = api_client.post("/api/v1/shift-rules", json=payload, headers={"Authorization": f"Bearer {token}"})
        rule_id = created.json()["data"]["id"]
        assert api_client.post(f"/api/v1/shift-rules/{rule_id}/publish", headers={"Authorization": f"Bearer {token}"}).status_code == 200

        edited = api_client.put(f"/api/v1/shift-rules/{rule_id}", json={"name": "已编辑", "days": payload["days"]}, headers={"Authorization": f"Bearer {token}"})

        assert edited.status_code == 200
        assert edited.json()["data"]["status"] == "published"
        assert edited.json()["data"]["latest_version_status"] == "draft"
        assert api_client.post(f"/api/v1/shift-rules/{rule_id}/publish", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_updating_published_rule_start_date_creates_draft_snapshot(self, db_session) -> None:
        room = OrgUnit(code="snapshot-room", name="快照机房", type="room")
        person = Person(
            code="snapshot-operator", name="快照值班员", org_unit=room,
            participate_schedule=True, person_type="duty_operator",
        )
        shift = ShiftDef(
            org_unit=room, code="snapshot-shift", name="快照班",
            start_time="08:00", end_time="16:00",
        )
        db_session.add_all([room, person, shift])
        db_session.commit()
        original_start = (date.today() + timedelta(days=40)).isoformat()
        updated_start = (date.today() + timedelta(days=50)).isoformat()
        rule = create_shift_rule(
            db_session, "snapshot-rule", "快照规则", cycle_days=1,
            start_date=original_start, persons_per_cell=1, org_unit_id=room.id,
            days=[{"day_no": 1, "cells": [{"shift_def_id": shift.id, "person_ids": [person.id]}]}],
        )
        publish_shift_rule(db_session, rule.id)
        db_session.commit()

        update_shift_rule(db_session, rule.id, start_date=updated_start)

        versions = list(db_session.scalars(
            select(ShiftRuleVersion)
            .where(ShiftRuleVersion.rule_id == rule.id)
            .order_by(ShiftRuleVersion.version_no)
        ))
        assert rule.status == "published"
        assert [(version.status, version.start_date) for version in versions] == [
            ("published", original_start),
            ("draft", updated_start),
        ]


class TestScheduleGeneration:
    """M3-P1: 规则发布生成排班"""

    def _setup_org_with_persons(self, db_session):
        from app.models.organization import OrgUnit
        from app.models.person import Person

        org = OrgUnit(code="room_gen", name="生成测试机房", type="room")
        p1 = Person(code="G001", name="张三", person_type="duty_operator", org_unit=org,
                    participate_schedule=True)
        p2 = Person(code="G002", name="李四", person_type="duty_operator", org_unit=org,
                    participate_schedule=True)
        db_session.add_all([org, p1, p2])
        db_session.commit()
        return org, [p1, p2]

    def _create_shift_defs(self, db_session, org):
        from app.models.shift import ShiftDef
        early = ShiftDef(org_unit_id=org.id, code="early", name="早班", start_time="00:00", end_time="08:00", display_order=1)
        mid = ShiftDef(org_unit_id=org.id, code="mid", name="中班", start_time="08:00", end_time="16:00", display_order=2)
        late = ShiftDef(org_unit_id=org.id, code="late", name="晚班", start_time="16:00", end_time="00:00", display_order=3)
        db_session.add_all([early, mid, late])
        db_session.commit()
        return early, mid, late

    def test_publish_generates_schedule(self, api_client: TestClient, db_session) -> None:
        org, persons = self._setup_org_with_persons(db_session)
        _, token = _create_admin(api_client, db_session)

        resp = api_client.post("/api/v1/shift-rules", json={
            "code": "rule_gen1", "name": "生成测试",
            "cycle_days": 2, "start_date": "2027-06-01", "persons_per_cell": 2,
            "org_unit_id": org.id,
            "days": [
                {"day_no": 1, "cells": [
                    {"shift_def_id": 1, "person_ids": [persons[0].id, persons[1].id]},
                ]},
                {"day_no": 2, "cells": [
                    {"shift_def_id": 1, "person_ids": [persons[1].id, persons[0].id]},
                ]},
            ],
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        rule_id = resp.json()["data"]["id"]

        resp = api_client.post(f"/api/v1/shift-rules/{rule_id}/publish",
                               headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "published"

        from app.models.schedule import MonthlySchedule, ScheduleDay
        schedule = db_session.query(MonthlySchedule).filter(
            MonthlySchedule.org_unit_id == org.id
        ).first()
        assert schedule is not None
        assert schedule.status == "published"
        days = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == schedule.id
        ).order_by(ScheduleDay.duty_date).all()
        assert len(days) > 0

    def test_publish_requires_rule_version(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post("/api/v1/shift-rules", json={
            "code": "rule_noorg", "name": "未保存版本",
            "cycle_days": 1, "start_date": "2027-07-01", "persons_per_cell": 1,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        rule_id = resp.json()["data"]["id"]

        resp = api_client.post(f"/api/v1/shift-rules/{rule_id}/publish",
                               headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422

    # ── M3-P1-T3: 排班生成专项测试 ──

    def test_multi_cycle_repeats_pattern(self, db_session) -> None:
        """M3-P1-T3: N=3 天循环 10 天，Day 4 应与 Day 1 相同"""
        from datetime import date as _date
        from app.services.schedule import generate_schedule_from_rule

        org, persons = self._setup_org_with_persons(db_session)
        early, mid, late = self._create_shift_defs(db_session, org)

        rule = ShiftRule(
            code="r_cycle", name="循环测试",
            cycle_days=3, start_date="2026-12-01", persons_per_cell=1,
            org_unit_id=org.id, status="draft",
        )
        db_session.add(rule)
        db_session.flush()

        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1,
            cycle_days=rule.cycle_days, start_date=rule.start_date,
            persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()

        # Day 1: early=P1, mid=P1, late=P2
        # Day 2: early=P2, mid=P2, late=P1
        # Day 3: early=P1, mid=P2, late=P1
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=1, cell_persons={
            str(early.id): [persons[0].id], str(mid.id): [persons[0].id], str(late.id): [persons[1].id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=2, cell_persons={
            str(early.id): [persons[1].id], str(mid.id): [persons[1].id], str(late.id): [persons[0].id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=3, cell_persons={
            str(early.id): [persons[0].id], str(mid.id): [persons[1].id], str(late.id): [persons[0].id],
        }))
        db_session.commit()

        # generate 10 days
        generate_schedule_from_rule(db_session, rule, v, total_days=10)

        from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
        ms = db_session.query(MonthlySchedule).filter(
            MonthlySchedule.org_unit_id == org.id
        ).first()
        assert ms is not None

        days = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == ms.id
        ).order_by(ScheduleDay.duty_date).all()
        assert len(days) == 11  # from 12/01 to 12/11 inclusive

        def _first_person(day, sdef):
            shifts = db_session.query(ScheduleShift).filter(
                ScheduleShift.schedule_day_id == day.id,
                ScheduleShift.shift_def_id == sdef.id,
            ).all()
            assert len(shifts) == 1
            spa = db_session.query(ScheduleShiftPerson).filter(
                ScheduleShiftPerson.schedule_shift_id == shifts[0].id,
            ).order_by(ScheduleShiftPerson.position_no).all()
            return spa[0].person_id

        d1_early = _first_person(days[0], early)  # Dec 1
        d4_early = _first_person(days[3], early)  # Dec 4 = (Dec 4 - Dec 1) = 3 days, 3 % 3 = 0
        assert d1_early == d4_early

    def test_cross_midnight_shift_ends_on_next_date(self, db_session) -> None:
        from app.services.schedule import generate_schedule_from_rule

        org, persons = self._setup_org_with_persons(db_session)
        overnight = ShiftDef(org_unit_id=org.id, code="overnight", name="夜班", start_time="20:00", end_time="08:00")
        rule = ShiftRule(code="overnight_rule", name="跨夜规则", cycle_days=1, start_date="2026-12-01", persons_per_cell=1, org_unit_id=org.id)
        db_session.add_all([overnight, rule])
        db_session.flush()
        version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date=rule.start_date, persons_per_cell=1, snapshot={"days": []}, status="published")
        db_session.add(version)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=version.id, day_no=1, cell_persons={str(overnight.id): [persons[0].id]}))
        db_session.commit()

        generate_schedule_from_rule(db_session, rule, version, total_days=0)

        from app.models.schedule import ScheduleDay, ScheduleShift

        shift = db_session.scalar(select(ScheduleShift).join(ScheduleDay).where(ScheduleDay.duty_date == date(2026, 12, 1)))
        assert shift is not None
        assert shift.end_at.date() == date(2026, 12, 2)

    def test_cross_month_continuity(self, db_session) -> None:
        """M3-P1-T3: 7 月 30 日起生成，8 月日期正确延续"""
        from datetime import date as _date
        from app.services.schedule import generate_schedule_from_rule

        org, persons = self._setup_org_with_persons(db_session)
        early, _mid, _late = self._create_shift_defs(db_session, org)

        rule = ShiftRule(
            code="r_month", name="跨月测试",
            cycle_days=2, start_date="2026-07-30", persons_per_cell=1,
            org_unit_id=org.id, status="draft",
        )
        db_session.add(rule)
        db_session.flush()

        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1,
            cycle_days=rule.cycle_days, start_date=rule.start_date,
            persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=1, cell_persons={
            str(early.id): [persons[0].id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=2, cell_persons={
            str(early.id): [persons[1].id],
        }))
        db_session.commit()

        generate_schedule_from_rule(db_session, rule, v, total_days=5)

        from app.models.schedule import MonthlySchedule, ScheduleDay
        ms = db_session.query(MonthlySchedule).filter(
            MonthlySchedule.org_unit_id == org.id
        ).first()
        assert ms is not None

        days = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == ms.id
        ).order_by(ScheduleDay.duty_date).all()
        dates = [d.duty_date for d in days]
        assert _date(2026, 7, 30) in dates
        assert _date(2026, 7, 31) in dates
        assert _date(2026, 8, 1) in dates
        assert _date(2026, 8, 2) in dates
        assert _date(2026, 8, 3) in dates
        assert _date(2026, 8, 4) in dates

    def test_holiday_flagging(self, db_session) -> None:
        """M3-P1-T3: 节假日日期 is_legal_holiday=True, holiday_name 正确"""
        from datetime import date as _date
        from app.models.holiday import HolidayCalendar
        from app.services.schedule import generate_schedule_from_rule

        org, persons = self._setup_org_with_persons(db_session)
        early, _mid, _late = self._create_shift_defs(db_session, org)

        db_session.add(HolidayCalendar(
            holiday_date=_date(2026, 10, 1), holiday_name="国庆节",
            year=2026, is_legal=True, status="enabled",
        ))
        db_session.add(HolidayCalendar(
            holiday_date=_date(2026, 10, 2), holiday_name="国庆节",
            year=2026, is_legal=True, status="enabled",
        ))
        db_session.commit()

        rule = ShiftRule(
            code="r_holiday", name="节假日测试",
            cycle_days=1, start_date="2026-10-01", persons_per_cell=1,
            org_unit_id=org.id, status="draft",
        )
        db_session.add(rule)
        db_session.flush()

        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1,
            cycle_days=rule.cycle_days, start_date=rule.start_date,
            persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=1, cell_persons={
            str(early.id): [persons[0].id],
        }))
        db_session.commit()

        generate_schedule_from_rule(db_session, rule, v, total_days=3)

        from app.models.schedule import MonthlySchedule, ScheduleDay
        ms = db_session.query(MonthlySchedule).filter(
            MonthlySchedule.org_unit_id == org.id
        ).first()
        days = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == ms.id
        ).order_by(ScheduleDay.duty_date).all()

        d1 = next(d for d in days if d.duty_date == _date(2026, 10, 1))
        assert d1.is_legal_holiday is True
        assert d1.holiday_name == "国庆节"

        d2 = next(d for d in days if d.duty_date == _date(2026, 10, 2))
        assert d2.is_legal_holiday is True
        assert d2.holiday_name == "国庆节"

        d3 = next(d for d in days if d.duty_date == _date(2026, 10, 3))
        assert d3.is_legal_holiday is False
        assert d3.holiday_name is None

    def test_republish_overwrites_future(self, db_session) -> None:
        """M3-P1-T3: 重新发布刷新未来排班"""
        from datetime import date as _date
        from app.services.schedule import generate_schedule_from_rule

        org, persons = self._setup_org_with_persons(db_session)
        early, _mid, _late = self._create_shift_defs(db_session, org)

        rule = ShiftRule(
            code="r_repub", name="重新发布测试",
            cycle_days=2, start_date="2026-12-01", persons_per_cell=1,
            org_unit_id=org.id, status="draft",
        )
        db_session.add(rule)
        db_session.flush()

        v1 = ShiftRuleVersion(
            rule_id=rule.id, version_no=1,
            cycle_days=rule.cycle_days, start_date=rule.start_date,
            persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v1)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=v1.id, day_no=1, cell_persons={
            str(early.id): [persons[0].id],
        }))
        db_session.add(ShiftRuleItem(version_id=v1.id, day_no=2, cell_persons={
            str(early.id): [persons[0].id],
        }))
        db_session.commit()

        generate_schedule_from_rule(db_session, rule, v1, total_days=3)

        from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
        ms = db_session.query(MonthlySchedule).filter(
            MonthlySchedule.org_unit_id == org.id
        ).first()

        # change to v2 — Day 2 now uses person[1]
        v2 = ShiftRuleVersion(
            rule_id=rule.id, version_no=2,
            cycle_days=rule.cycle_days, start_date=rule.start_date,
            persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v2)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=v2.id, day_no=1, cell_persons={
            str(early.id): [persons[0].id],
        }))
        db_session.add(ShiftRuleItem(version_id=v2.id, day_no=2, cell_persons={
            str(early.id): [persons[1].id],
        }))
        db_session.commit()

        generate_schedule_from_rule(db_session, rule, v2, total_days=3)

        days = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == ms.id
        ).order_by(ScheduleDay.duty_date).all()
        assert len(days) >= 3

        day2 = next(d for d in days if d.duty_date == _date(2026, 12, 2))
        shift = db_session.query(ScheduleShift).filter(
            ScheduleShift.schedule_day_id == day2.id
        ).first()
        sp = db_session.query(ScheduleShiftPerson).filter(
            ScheduleShiftPerson.schedule_shift_id == shift.id
        ).first()
        assert sp.person_id == persons[1].id


class TestPersonFilter:
    """人员列表过滤参数"""

    def _setup_admin_with_person_permission(self, api_client: TestClient, db_session) -> str:
        from app.models.user import SysDataScope, SysPermission, SysRole
        from app.services.auth import create_user as _cu

        user = _cu(db_session, "padmin", "password123", "人员管理")
        perm_shift = SysPermission(code="shift:rule:view", name="Shift", type="api")
        perm_person = SysPermission(code="person:manage:view", name="Person", type="api")
        role = SysRole(code="prole", name="PRole")
        role.permissions.extend([perm_shift, perm_person])
        db_session.add_all([perm_shift, perm_person, role])
        db_session.flush()
        user.roles.append(role)
        db_session.add(SysDataScope(user_id=user.id, scope_type="all", org_unit_id=None))
        db_session.commit()
        token = _login(api_client, db_session, "padmin", "password123")
        room = db_session.scalars(select(OrgUnit).where(OrgUnit.type == "room")).first()
        assert room is not None
        api_client.headers["X-Current-Room-Id"] = str(room.id)
        return token

    def test_filter_by_participate_schedule(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit
        from app.models.person import Person

        org = OrgUnit(code="org_f1", name="过滤测试", type="room")
        p1 = Person(code="F001", name="参与排班", person_type="duty_operator", org_unit=org,
                    participate_schedule=True)
        p2 = Person(code="F002", name="不参与", person_type="maintenance", org_unit=org,
                    participate_schedule=False)
        db_session.add_all([org, p1, p2])
        db_session.commit()

        token = self._setup_admin_with_person_permission(api_client, db_session)
        resp = api_client.get("/api/v1/persons?participate_schedule=true",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        codes = [p["code"] for p in data]
        assert "F001" in codes
        assert "F002" not in codes

    def test_filter_by_org_unit(self, api_client: TestClient, db_session) -> None:
        from app.models.organization import OrgUnit
        from app.models.person import Person

        org1 = OrgUnit(code="org_g1", name="机房1", type="room")
        org2 = OrgUnit(code="org_g2", name="机房2", type="room")
        p1 = Person(code="G001", name="人1", person_type="duty_operator", org_unit=org1,
                    participate_schedule=True)
        p2 = Person(code="G002", name="人2", person_type="duty_operator", org_unit=org2,
                    participate_schedule=True)
        db_session.add_all([org1, org2, p1, p2])
        db_session.commit()

        token = self._setup_admin_with_person_permission(api_client, db_session)
        resp = api_client.get(f"/api/v1/persons?org_unit_id={org1.id}",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        codes = [p["code"] for p in data]
        assert "G001" in codes
        assert "G002" not in codes
