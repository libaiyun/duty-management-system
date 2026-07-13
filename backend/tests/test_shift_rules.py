import pytest
from fastapi.testclient import TestClient

from app.models.organization import OrgUnit
from app.models.shift import ShiftRule, ShiftRuleItem, ShiftRuleVersion
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


def _sample_days(cycle_days: int = 6) -> list[dict]:
    days = []
    for day_no in range(1, cycle_days + 1):
        cells = []
        for shift_id in range(1, 4):
            cells.append({
                "shift_def_id": shift_id,
                "person_ids": list(range(100 + day_no * 10 + shift_id, 100 + day_no * 10 + shift_id + 2)),
            })
        days.append({"day_no": day_no, "cells": cells})
    return days


def _create_org(db_session) -> OrgUnit:
    org = OrgUnit(code="ORG1", name="测试机房", type="room")
    db_session.add(org)
    db_session.commit()
    return org


class TestShiftRuleApi:
    def test_list_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/shift-rules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_create_rule_with_days(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_01",
                "name": "广播发射台规则",
                "cycle_days": 6,
                "start_date": "2026-07-17",
                "persons_per_cell": 2,
                "days": _sample_days(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["code"] == "rule_01"
        assert data["cycle_days"] == 6
        assert data["start_date"] == "2026-07-17"
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

    def test_create_rule_with_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_03",
                "name": "有机房规则",
                "cycle_days": 5,
                "start_date": "2026-09-01",
                "persons_per_cell": 1,
                "org_unit_id": org.id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["org_unit_id"] == org.id

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
        assert resp.status_code == 404

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
        resp = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "rule_pub",
                "name": "可发布规则",
                "cycle_days": 6,
                "start_date": "2026-07-17",
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
        days = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == schedule.id
        ).order_by(ScheduleDay.duty_date).all()
        assert len(days) > 0

    def test_publish_without_org_skips_generation(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post("/api/v1/shift-rules", json={
            "code": "rule_noorg", "name": "无机房",
            "cycle_days": 1, "start_date": "2027-07-01", "persons_per_cell": 1,
            "days": [{"day_no": 1, "cells": [{"shift_def_id": 1, "person_ids": [1]}]}],
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        rule_id = resp.json()["data"]["id"]

        resp = api_client.post(f"/api/v1/shift-rules/{rule_id}/publish",
                               headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "published"


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
        return _login(api_client, db_session, "padmin", "password123")

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
