from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysDataScope, SysPermission, SysRole
from app.services.auth import create_user

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, db_session, username: str, password: str) -> str:
    resp = api_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _create_admin(api_client: TestClient, db_session) -> tuple[int, str]:
    user = create_user(db_session, "admin", "password123", "管理员")
    perm = SysPermission(code="schedule:monthly:view", name="View Schedule", type="api")
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.append(perm)
    db_session.add_all([perm, role])
    user.roles.append(role)
    db_session.flush()
    db_session.add(SysDataScope(user_id=user.id, scope_type="all", org_unit_id=None))
    db_session.commit()
    token = _login(api_client, db_session, "admin", "password123")
    return user.id, token


def _create_scoped_user(api_client: TestClient, db_session, username: str, org_unit_id: int) -> tuple[int, str]:
    user = create_user(db_session, username, "password123", username)
    perm = SysPermission(code="schedule:monthly:view", name="View Schedule", type="api")
    role = SysRole(code=f"role-{username}", name=username)
    role.permissions.append(perm)
    db_session.add_all([perm, role])
    user.roles.append(role)
    db_session.flush()
    db_session.add(SysDataScope(user_id=user.id, scope_type="room", org_unit_id=org_unit_id))
    db_session.commit()
    token = _login(api_client, db_session, username, "password123")
    return user.id, token


def _create_org(db_session, code: str = "test-station", name: str = "测试台站", org_type: str = "station",
                parent_id: int | None = None) -> OrgUnit:
    org = OrgUnit(code=code, name=name, type=org_type, parent_id=parent_id)
    db_session.add(org)
    db_session.commit()
    return org


def _create_shift_def(db_session, code: str = "early", name: str = "早班") -> ShiftDef:
    sd = ShiftDef(code=code, name=name, start_time="00:00", end_time="08:00")
    db_session.add(sd)
    db_session.commit()
    return sd


def _create_rule(db_session) -> ShiftRule:
    rule = ShiftRule(
        code="rule-broadcast", name="广播规则", cycle_days=6,
        start_date="2026-06-01", persons_per_cell=2,
    )
    db_session.add(rule)
    db_session.commit()
    return rule


def _create_person(db_session, org: OrgUnit, code: str = "P001", name: str = "值班员") -> Person:
    person = Person(code=code, name=name, person_type="duty_operator", org_unit=org,
                    participate_schedule=True)
    db_session.add(person)
    db_session.commit()
    return person


def _build_full_schedule(db_session, org: OrgUnit, rule: ShiftRule, shift_defs: list[ShiftDef],
                         persons: list[Person], status: str = "draft") -> MonthlySchedule:
    # count existing versions to generate unique version_no
    from sqlalchemy import select as sa_select, func
    existing_versions = db_session.scalar(
        sa_select(func.count()).select_from(ShiftRuleVersion.__table__)
        .where(ShiftRuleVersion.rule_id == rule.id)
    ) or 0
    rule_version = ShiftRuleVersion(
        rule_id=rule.id, version_no=existing_versions + 1, cycle_days=rule.cycle_days,
        start_date=rule.start_date, persons_per_cell=rule.persons_per_cell,
        snapshot={"days": []},
    )
    db_session.add(rule_version)
    db_session.flush()

    ms = MonthlySchedule(
        org_unit_id=org.id, rule_id=rule.id, rule_version_id=rule_version.id, status=status,
        generated_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    db_session.add(ms)
    db_session.flush()

    for day_num in range(1, 4):
        day = ScheduleDay(
            schedule_id=ms.id,
            duty_date=date(2026, 7, day_num),
            weekday=(day_num + 6) % 7,
            is_legal_holiday=(day_num == 4),
            holiday_name="国庆节" if day_num == 4 else None,
        )
        db_session.add(day)
        db_session.flush()

        for sd in shift_defs:
            shift = ScheduleShift(
                schedule_day_id=day.id,
                shift_def_id=sd.id,
                start_at=datetime(2026, 7, day_num, tzinfo=UTC),
                end_at=datetime(2026, 7, day_num, 8, tzinfo=UTC),
                status="normal",
            )
            db_session.add(shift)
            db_session.flush()

            for pos, person in enumerate(persons, 1):
                db_session.add(ScheduleShiftPerson(
                    schedule_shift_id=shift.id,
                    person_id=person.id,
                    position_no=pos,
                    source_type="auto",
                ))

    db_session.commit()
    return ms


class TestScheduleListApi:
    def test_list_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_data(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session, "early", "早班")
        p1 = _create_person(db_session, org, "P001", "张三")
        p2 = _create_person(db_session, org, "P002", "李四")
        _build_full_schedule(db_session, org, rule, [early], [p1, p2])

        resp = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        items = data["items"]
        assert len(items) == 1
        s = items[0]
        assert s["org_unit_code"] == org.code
        assert s["org_unit_name"] == org.name
        assert s["rule_code"] == rule.code
        assert s["rule_name"] == rule.name
        assert s["status"] == "draft"
        assert s["day_count"] == 3
        assert s["shift_count"] == 3
        assert s["person_count"] == 6
        assert s["generated_at"] is not None

    def test_list_filter_by_status(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org_a, "P001", "张三")
        p2 = _create_person(db_session, org_b, "P002", "李四")
        _build_full_schedule(db_session, org_a, rule, [early], [p1], status="draft")
        _build_full_schedule(db_session, org_b, rule, [early], [p2], status="published")

        resp = api_client.get("/api/v1/schedules?status=published",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["status"] == "published"

    def test_list_filter_by_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org_a, "P001", "张三")
        p2 = _create_person(db_session, org_b, "P002", "李四")
        _build_full_schedule(db_session, org_a, rule, [early], [p1])
        _build_full_schedule(db_session, org_b, rule, [early], [p2])

        resp = api_client.get(f"/api/v1/schedules?org_unit_id={org_a.id}",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["org_unit_code"] == org_a.code

    def test_list_pagination(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        org_c = _create_org(db_session, "station-c", "台站C")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org_a, "P001", "张三")
        _build_full_schedule(db_session, org_a, rule, [early], [p1])
        _build_full_schedule(db_session, org_b, rule, [early], [p1])
        _build_full_schedule(db_session, org_c, rule, [early], [p1])

        resp = api_client.get("/api/v1/schedules?page=1&page_size=2",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 3
        assert data["total_pages"] == 2
        assert len(data["items"]) == 2

    def test_list_requires_permission(self, api_client: TestClient, db_session) -> None:
        create_user(db_session, "worker", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker", "pass")
        resp = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_list_data_scope_room(self, api_client: TestClient, db_session) -> None:
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org_a, "P001", "张三")
        p2 = _create_person(db_session, org_b, "P002", "李四")
        _build_full_schedule(db_session, org_a, rule, [early], [p1])
        _build_full_schedule(db_session, org_b, rule, [early], [p2])

        _, token = _create_scoped_user(api_client, db_session, "room-user", org_a.id)

        resp = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["org_unit_code"] == org_a.code

    def test_list_data_scope_none(self, api_client: TestClient, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        _build_full_schedule(db_session, org, rule, [early], [p1])

        user = create_user(db_session, "no-scope", "password123", "无范围")
        perm = SysPermission(code="schedule:monthly:view", name="View Schedule", type="api")
        role = SysRole(code="role-no-scope", name="NoScope")
        role.permissions.append(perm)
        db_session.add_all([perm, role])
        user.roles.append(role)
        db_session.commit()
        token = _login(api_client, db_session, "no-scope", "password123")

        resp = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []

    def test_list_org_outside_scope_returns_empty(self, api_client: TestClient, db_session) -> None:
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org_a, "P001", "张三")
        _build_full_schedule(db_session, org_a, rule, [early], [p1])

        _, token = _create_scoped_user(api_client, db_session, "room-user", org_a.id)

        resp = api_client.get(f"/api/v1/schedules?org_unit_id={org_b.id}",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["items"] == []


class TestScheduleDetailApi:
    def test_get_detail(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        resp = api_client.get(f"/api/v1/schedules/{ms.id}",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == ms.id
        assert data["org_unit_code"] == org.code
        assert data["rule_name"] == rule.name
        assert data["status"] == "draft"
        assert data["day_count"] == 3

    def test_get_detail_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/schedules/99999",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_get_detail_requires_permission(self, api_client: TestClient, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        create_user(db_session, "worker2", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker2", "pass")
        resp = api_client.get(f"/api/v1/schedules/{ms.id}",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestScheduleDaysApi:
    def test_get_days(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session, "early", "早班")
        p1 = _create_person(db_session, org, "P001", "张三")
        p2 = _create_person(db_session, org, "P002", "李四")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1, p2])

        resp = api_client.get(f"/api/v1/schedules/{ms.id}/days",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        days = resp.json()["data"]
        assert len(days) == 3

        day = days[0]
        assert day["duty_date"] == "2026-07-01"
        assert day["weekday"] == 0
        assert day["is_legal_holiday"] is False
        assert day["holiday_name"] is None
        assert len(day["shifts"]) == 1

        shift = day["shifts"][0]
        assert shift["shift_def_code"] == "early"
        assert shift["shift_def_name"] == "早班"
        assert shift["status"] == "normal"
        assert len(shift["persons"]) == 2

    def test_get_days_empty(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        rule_version = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=rule.cycle_days,
            start_date=rule.start_date, persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []},
        )
        db_session.add(rule_version)
        db_session.flush()
        ms = MonthlySchedule(
            org_unit_id=org.id, rule_id=rule.id, rule_version_id=rule_version.id,
            status="draft",
        )
        db_session.add(ms)
        db_session.commit()

        resp = api_client.get(f"/api/v1/schedules/{ms.id}/days",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_get_days_not_found(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get("/api/v1/schedules/99999/days",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_days_requires_permission(self, api_client: TestClient, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        create_user(db_session, "worker3", "pass", "普通用户")
        db_session.commit()
        token = _login(api_client, db_session, "worker3", "pass")
        resp = api_client.get(f"/api/v1/schedules/{ms.id}/days",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_get_days_filter_by_month(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: 按月过滤日班次明细"""
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session, "early", "早班")
        mid = _create_shift_def(db_session, "mid", "中班")
        p1 = _create_person(db_session, org, "P001", "张三")
        p2 = _create_person(db_session, org, "P002", "李四")

        rule_version = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=rule.cycle_days,
            start_date=rule.start_date, persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []},
        )
        db_session.add(rule_version)
        db_session.flush()

        ms = MonthlySchedule(
            org_unit_id=org.id, rule_id=rule.id, rule_version_id=rule_version.id,
            status="draft",
        )
        db_session.add(ms)
        db_session.flush()

        for day_num in range(1, 4):
            day = ScheduleDay(
                schedule_id=ms.id,
                duty_date=date(2026, 7, day_num),
                weekday=(day_num + 6) % 7,
            )
            db_session.add(day)
            db_session.flush()
            for sd in [early, mid]:
                shift = ScheduleShift(
                    schedule_day_id=day.id, shift_def_id=sd.id,
                    start_at=datetime(2026, 7, day_num, tzinfo=UTC),
                    end_at=datetime(2026, 7, day_num, 8, tzinfo=UTC),
                    status="normal",
                )
                db_session.add(shift)
                db_session.flush()
                for pos, p in enumerate([p1, p2], 1):
                    db_session.add(ScheduleShiftPerson(
                        schedule_shift_id=shift.id, person_id=p.id,
                        position_no=pos, source_type="auto",
                    ))
        db_session.commit()

        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days?year=2026&month=7",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        days = resp.json()["data"]
        assert len(days) == 3

    def test_get_days_filter_by_month_empty(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: 按月过滤 - 无匹配月份"""
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days?year=2026&month=8",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_get_days_year_without_month(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: 仅传 year 不传 month 返回 422"""
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days?year=2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_get_days_month_without_year(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: 仅传 month 不传 year 返回 422"""
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days?month=7",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


class TestScheduleDaysRangeApi:
    """M3-P1-T2: 按日期范围查询日班次明细"""

    def test_get_days_range(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session, "early", "早班")
        mid = _create_shift_def(db_session, "mid", "中班")
        p1 = _create_person(db_session, org, "P001", "张三")
        p2 = _create_person(db_session, org, "P002", "李四")
        ms = _build_full_schedule(db_session, org, rule, [early, mid], [p1, p2])

        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days/range",
            params={"from": "2026-07-01", "to": "2026-07-02"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        days = resp.json()["data"]
        assert len(days) == 2
        assert days[0]["duty_date"] == "2026-07-01"
        assert days[1]["duty_date"] == "2026-07-02"

    def test_get_days_range_empty(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: 日期范围无匹配"""
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days/range",
            params={"from": "2025-01-01", "to": "2025-01-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_get_days_range_from_after_to(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: from > to 返回错误"""
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days/range",
            params={"from": "2026-12-31", "to": "2026-01-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_get_days_range_schedule_not_found(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: range 端点 404"""
        _, token = _create_admin(api_client, db_session)
        resp = api_client.get(
            "/api/v1/schedules/99999/days/range",
            params={"from": "2026-07-01", "to": "2026-07-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_get_days_range_requires_permission(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T2: range 端点需要权限"""
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        create_user(db_session, "norange", "pass", "无权限")
        db_session.commit()
        token = _login(api_client, db_session, "norange", "pass")
        resp = api_client.get(
            f"/api/v1/schedules/{ms.id}/days/range",
            params={"from": "2026-07-01", "to": "2026-07-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
