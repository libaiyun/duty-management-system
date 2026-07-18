from datetime import UTC, date, datetime, timedelta

import pytest
from app.core.exceptions import BusinessRuleError
from app.models.holiday import HolidayCalendar
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import (
    DutyChangeLedger,
    MonthlySchedule,
    ScheduleDay,
    ScheduleRecalculationFlag,
    ScheduleShift,
    ScheduleShiftBaselinePerson,
    ScheduleShiftPerson,
)
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysDataScope, SysPermission, SysRole
from app.services.auth import create_user
from app.services.schedule import apply_historical_correction
from fastapi.testclient import TestClient
from sqlalchemy import select

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
    permissions = [
        SysPermission(code="schedule:monthly:view", name="View Schedule", type="api"),
        SysPermission(code="schedule:monthly:generate", name="Generate Schedule", type="api"),
        SysPermission(code="duty:actual:view", name="View Actual Duty", type="api"),
        SysPermission(code="shift:rule:view", name="View Shift Rule", type="api"),
        SysPermission(code="shift:rule:manage", name="Manage Shift Rule", type="api"),
    ]
    role = SysRole(code="admin-role", name="Admin")
    role.permissions.extend(permissions)
    db_session.add_all([*permissions, role])
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


def _create_scoped_user(api_client: TestClient, db_session, username: str, org_unit_id: int) -> tuple[int, str]:
    person = Person(code=f"{username}-person", name=username, person_type="duty_operator", org_unit_id=org_unit_id)
    db_session.add(person)
    db_session.flush()
    user = create_user(db_session, username, "password123", username, person_id=person.id)
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


def _create_org(db_session, code: str = "test-station", name: str = "测试机房", org_type: str = "room",
                parent_id: int | None = None) -> OrgUnit:
    current_room = db_session.scalar(
        select(OrgUnit).where(OrgUnit.code == "admin-current-room")
    )
    if current_room is not None:
        current_room.code = code
        current_room.name = name
        current_room.type = "room"
        current_room.parent_id = parent_id
        db_session.commit()
        return current_room
    org = OrgUnit(code=code, name=name, type=org_type, parent_id=parent_id)
    db_session.add(org)
    db_session.commit()
    return org


def _create_shift_def(db_session, code: str = "early", name: str = "早班") -> ShiftDef:
    sd = ShiftDef(org_unit_id=1, code=code, name=name, start_time="00:00", end_time="08:00")
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
    from sqlalchemy import func
    from sqlalchemy import select as sa_select
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


def _shift_id_for_date(db_session, schedule_id: int, *, historical: bool = False) -> int:
    comparison_date = date.today() - timedelta(days=1) if historical else date.today()
    statement = (
        select(ScheduleShift.id)
        .join(ScheduleDay)
        .where(ScheduleDay.schedule_id == schedule_id)
        .where(ScheduleDay.duty_date <= comparison_date if historical else ScheduleDay.duty_date >= comparison_date)
        .order_by(ScheduleDay.duty_date.desc() if historical else ScheduleDay.duty_date)
    )
    shift_id = db_session.scalar(statement)
    assert shift_id is not None
    return shift_id


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
        assert s["coverage_through"] == "2026-07-03"

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
        assert items == []

    def test_list_filter_by_org_unit(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org_a, "P001", "张三")
        p2 = _create_person(db_session, org_b, "P002", "李四")
        _build_full_schedule(db_session, org_a, rule, [early], [p1], status="published")
        _build_full_schedule(db_session, org_b, rule, [early], [p2], status="published")

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
        _build_full_schedule(db_session, org_a, rule, [early], [p1], status="published")
        _build_full_schedule(db_session, org_b, rule, [early], [p1])
        _build_full_schedule(db_session, org_c, rule, [early], [p1])

        resp = api_client.get("/api/v1/schedules?page=1&page_size=2",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["total_pages"] == 1
        assert len(data["items"]) == 1

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
        _build_full_schedule(db_session, org_a, rule, [early], [p1], status="published")
        _build_full_schedule(db_session, org_b, rule, [early], [p2], status="published")

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
        assert resp.status_code == 422
        assert resp.json()["code"] == "BUSINESS_RULE_FAILED"

    def test_list_org_outside_scope_returns_empty(self, api_client: TestClient, db_session) -> None:
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org_a, "P001", "张三")
        _build_full_schedule(db_session, org_a, rule, [early], [p1], status="published")

        _, token = _create_scoped_user(api_client, db_session, "room-user", org_a.id)

        resp = api_client.get(f"/api/v1/schedules?org_unit_id={org_b.id}",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) == 1


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

    def test_get_detail_rejects_schedule_outside_room_scope(self, api_client: TestClient, db_session) -> None:
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        person = _create_person(db_session, org_b, "P001", "张三")
        schedule = _build_full_schedule(db_session, org_b, rule, [early], [person])
        _, token = _create_scoped_user(api_client, db_session, "room-user", org_a.id)

        resp = api_client.get(
            f"/api/v1/schedules/{schedule.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404


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

    def test_get_days_uses_current_enabled_holiday_calendar(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session, "early", "早班")
        person = _create_person(db_session, org, "P001", "张三")
        schedule = _build_full_schedule(db_session, org, rule, [early], [person])
        db_session.add(HolidayCalendar(
            holiday_date=date(2026, 7, 1),
            holiday_name="建党节",
            year=2026,
            is_legal=True,
            status="enabled",
        ))
        stale_day = db_session.scalars(
            select(ScheduleDay).where(ScheduleDay.schedule_id == schedule.id, ScheduleDay.duty_date == date(2026, 7, 1))
        ).one()
        stale_day.is_legal_holiday = False
        stale_day.holiday_name = None
        db_session.commit()

        response = api_client.get(
            f"/api/v1/schedules/{schedule.id}/days?year=2026&month=7",
            headers={"Authorization": f"Bearer {token}"},
        )

        day = response.json()["data"][0]
        assert day["is_legal_holiday"] is True
        assert day["holiday_name"] == "建党节"

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

    def test_get_days_rejects_schedule_outside_room_scope(self, api_client: TestClient, db_session) -> None:
        org_a = _create_org(db_session, "station-a", "台站A")
        org_b = _create_org(db_session, "station-b", "台站B")
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        person = _create_person(db_session, org_b, "P001", "张三")
        schedule = _build_full_schedule(db_session, org_b, rule, [early], [person])
        _, token = _create_scoped_user(api_client, db_session, "room-user", org_a.id)

        resp = api_client.get(
            f"/api/v1/schedules/{schedule.id}/days",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404

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

    @pytest.mark.parametrize("query", ["year=0&month=1", "year=10000&month=1", "year=2026&month=0", "year=2026&month=13"])
    def test_get_days_rejects_invalid_month_query(self, api_client: TestClient, db_session, query: str) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = _build_full_schedule(db_session, org, rule, [], [])

        response = api_client.get(f"/api/v1/schedules/{ms.id}/days?{query}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 422
        assert response.json()["code"] == "BUSINESS_RULE_FAILED"


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

    def test_get_days_range_rejects_span_over_366_days(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = _build_full_schedule(db_session, org, rule, [], [])

        response = api_client.get(
            f"/api/v1/schedules/{ms.id}/days/range",
            params={"from": "2026-01-01", "to": "2027-01-02"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 422
        assert response.json()["code"] == "BUSINESS_RULE_FAILED"

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


class TestScheduleGenerateApi:
    """M3-P1-T4: 生成/刷新排班 API"""

    def test_publish_then_month_and_range_apis_return_full_room_data(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room = db_session.scalar(select(OrgUnit).where(OrgUnit.type == "room"))
        assert room is not None
        shift = ShiftDef(org_unit_id=room.id, code="publish-read", name="发布读取班", start_time="08:00", end_time="16:00")
        person = Person(code="PUBLISH-READ", name="完整值班员", person_type="duty_operator", org_unit_id=room.id, participate_schedule=True)
        db_session.add_all([shift, person])
        db_session.commit()
        start_date = date.today() + timedelta(days=1)

        created = api_client.post(
            "/api/v1/shift-rules",
            json={
                "code": "publish_read_rule", "name": "发布读取规则", "cycle_days": 1,
                "start_date": start_date.isoformat(), "persons_per_cell": 1,
                "days": [{"day_no": 1, "cells": [{"shift_def_id": shift.id, "person_ids": [person.id]}]}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert created.status_code == 200
        assert api_client.post(
            f"/api/v1/shift-rules/{created.json()['data']['id']}/publish",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code == 200

        listed = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        assert listed.status_code == 200
        schedule = listed.json()["data"]["items"][0]
        assert schedule["org_unit_id"] == room.id
        assert schedule["day_count"] > 0
        assert schedule["shift_count"] == schedule["day_count"]
        assert schedule["person_count"] == schedule["day_count"]

        month = api_client.get(
            f"/api/v1/schedules/{schedule['id']}/days?year={start_date.year}&month={start_date.month}",
            headers={"Authorization": f"Bearer {token}"},
        )
        ranged = api_client.get(
            f"/api/v1/schedules/{schedule['id']}/days/range",
            params={"from": start_date.isoformat(), "to": start_date.isoformat()},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert month.status_code == 200
        assert ranged.status_code == 200
        day = ranged.json()["data"][0]
        assert day["duty_date"] == start_date.isoformat()
        published_shift = next(item for item in day["shifts"] if item["shift_def_code"] == shift.code)
        assert published_shift["persons"] == [{
            "id": published_shift["persons"][0]["id"],
            "person_id": person.id,
            "person_code": person.code,
            "person_name": person.name,
            "position_no": 1,
            "source_type": "auto",
            "remark": None,
        }]

    def _setup_published_rule_with_schedule(self, db_session):
        from app.models.shift import ShiftRuleItem, ShiftRuleVersion

        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session, "early", "早班")
        p1 = _create_person(db_session, org, "P001", "张三")
        p2 = _create_person(db_session, org, "P002", "李四")

        rule.org_unit_id = org.id
        rule.status = "published"
        db_session.commit()

        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1,
            cycle_days=rule.cycle_days, start_date=rule.start_date,
            persons_per_cell=rule.persons_per_cell,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=1, cell_persons={
            str(early.id): [p1.id, p2.id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=2, cell_persons={
            str(early.id): [p2.id, p1.id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=3, cell_persons={
            str(early.id): [p1.id, p2.id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=4, cell_persons={
            str(early.id): [p2.id, p1.id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=5, cell_persons={
            str(early.id): [p1.id, p2.id],
        }))
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=6, cell_persons={
            str(early.id): [p2.id, p1.id],
        }))
        db_session.commit()

        ms = MonthlySchedule(
            org_unit_id=org.id, rule_id=rule.id, rule_version_id=v.id,
            status="draft",
        )
        db_session.add(ms)
        db_session.commit()
        return ms, rule, v, org, early, [p1, p2]

    def test_generate_creates_schedule_days(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T4: 生成排班日数据"""
        ms, _rule, _v, _org, _early, _persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)

        resp = api_client.post(
            f"/api/v1/schedules/{ms.id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "published"
        assert data["generated_at"] is not None
        assert data["day_count"] > 0

    def test_edit_keeps_original_baseline_and_writes_ledger(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        shift_id = _shift_id_for_date(db_session, ms.id)
        before_ids = db_session.scalars(
            select(ScheduleShiftPerson.person_id).where(ScheduleShiftPerson.schedule_shift_id == shift_id).order_by(ScheduleShiftPerson.position_no)
        ).all()
        edited = api_client.put(
            f"/api/v1/schedules/{ms.id}/shifts/{shift_id}/persons", json={"person_ids": list(reversed(before_ids))},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert edited.status_code == 200
        assert edited.json()["data"]["persons"][0]["source_type"] == "manual"
        from app.models.schedule import ScheduleChangeLog
        change = db_session.scalar(select(ScheduleChangeLog).where(ScheduleChangeLog.schedule_shift_id == shift_id))
        assert change is not None
        assert change.source_type == "manual"
        assert change.schedule_version == 2
        assert change.before_person_ids == before_ids
        assert change.after_person_ids == list(reversed(before_ids))
        assert api_client.post(f"/api/v1/schedules/{ms.id}/publish", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        baseline_ids = db_session.scalars(
            select(ScheduleShiftBaselinePerson.person_id).where(ScheduleShiftBaselinePerson.schedule_shift_id == shift_id).order_by(ScheduleShiftBaselinePerson.position_no)
        ).all()
        assert baseline_ids == before_ids
        ledger = api_client.get(
            f"/api/v1/schedules/change-ledger?from={date.today()}&to={date.today()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ledger.status_code == 200
        assert ledger.json()["data"]["total"] == 2
        assert {item["change_type"] for item in ledger.json()["data"]["items"]} == {"manual"}
        assert {item["created_by_name"] for item in ledger.json()["data"]["items"]} == {"管理员"}
        assert db_session.scalar(select(DutyChangeLedger).where(DutyChangeLedger.schedule_shift_id == shift_id)) is not None

    def test_edit_with_unchanged_persons_does_not_create_a_change_marker(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, _persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        shift_id = _shift_id_for_date(db_session, ms.id)
        current_ids = db_session.scalars(
            select(ScheduleShiftPerson.person_id)
            .where(ScheduleShiftPerson.schedule_shift_id == shift_id)
            .order_by(ScheduleShiftPerson.position_no)
        ).all()

        response = api_client.put(
            f"/api/v1/schedules/{ms.id}/shifts/{shift_id}/persons", json={"person_ids": current_ids},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert {person["source_type"] for person in response.json()["data"]["persons"]} == {"auto"}
        assert db_session.get(MonthlySchedule, ms.id).version == 1
        assert db_session.scalar(select(DutyChangeLedger).where(DutyChangeLedger.schedule_shift_id == shift_id)) is None

    def test_edit_does_not_use_schedule_lock_as_a_date_operation_guard(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        db_session.get(MonthlySchedule, ms.id).status = "locked"
        db_session.commit()
        shift_id = _shift_id_for_date(db_session, ms.id)
        response = api_client.put(
            f"/api/v1/schedules/{ms.id}/shifts/{shift_id}/persons", json={"person_ids": [persons[0].id, persons[1].id]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_normal_edit_rejects_historical_shift(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        shift_id = _shift_id_for_date(db_session, ms.id, historical=True)
        response = api_client.put(
            f"/api/v1/schedules/{ms.id}/shifts/{shift_id}/persons", json={"person_ids": [persons[1].id, persons[0].id]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422
        assert "历史班次" in response.json()["message"]

    def test_historical_correction_requires_director_role(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        shift_id = _shift_id_for_date(db_session, ms.id, historical=True)
        response = api_client.post(
            f"/api/v1/schedules/{ms.id}/shifts/{shift_id}/history-corrections",
            json={"person_ids": [persons[1].id, persons[0].id], "reason": "补录历史调整"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_historical_correction_marks_month_for_recalculation(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        shift_id = _shift_id_for_date(db_session, ms.id, historical=True)
        schedule = db_session.get(MonthlySchedule, ms.id)
        shift = db_session.get(ScheduleShift, shift_id)
        assert schedule is not None and shift is not None
        apply_historical_correction(db_session, schedule, shift, [persons[1].id, persons[0].id], "补录历史调整", actor_id=1)
        db_session.commit()
        flag = db_session.scalar(select(ScheduleRecalculationFlag).where(
            ScheduleRecalculationFlag.org_unit_id == schedule.org_unit_id,
            ScheduleRecalculationFlag.year_month == shift.schedule_day.duty_date.strftime("%Y-%m"),
        ))
        assert flag is not None
        assert flag.status == "required"

    def test_historical_correction_rejects_unchanged_final_schedule(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        shift_id = _shift_id_for_date(db_session, ms.id, historical=True)
        schedule = db_session.get(MonthlySchedule, ms.id)
        shift = db_session.get(ScheduleShift, shift_id)
        assert schedule is not None and shift is not None
        current_ids = db_session.scalars(
            select(ScheduleShiftPerson.person_id)
            .where(ScheduleShiftPerson.schedule_shift_id == shift_id)
            .order_by(ScheduleShiftPerson.position_no)
        ).all()

        with pytest.raises(BusinessRuleError, match="与当前最终排班一致"):
            apply_historical_correction(db_session, schedule, shift, current_ids, "无需调整", actor_id=1)

        assert db_session.scalar(select(ScheduleRecalculationFlag).where(
            ScheduleRecalculationFlag.org_unit_id == schedule.org_unit_id,
            ScheduleRecalculationFlag.year_month == shift.schedule_day.duty_date.strftime("%Y-%m"),
        )) is None

    def test_edit_rejects_changed_staff_count(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, _org, _early, persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        assert api_client.post(f"/api/v1/schedules/{ms.id}/generate", headers={"Authorization": f"Bearer {token}"}).status_code == 200
        shift_id = _shift_id_for_date(db_session, ms.id)
        response = api_client.put(
            f"/api/v1/schedules/{ms.id}/shifts/{shift_id}/persons", json={"person_ids": [persons[0].id]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422
        assert response.json()["message"] == "值班人员数量必须保持为 2 人"

    def test_duty_operator_cannot_view_draft_schedule(self, api_client: TestClient, db_session) -> None:
        ms, _rule, _version, org, _early, _persons = self._setup_published_rule_with_schedule(db_session)
        user_id, token = _create_scoped_user(api_client, db_session, "draft-reader", org.id)
        assert user_id
        listed = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})
        detail = api_client.get(f"/api/v1/schedules/{ms.id}", headers={"Authorization": f"Bearer {token}"})
        assert listed.status_code == 200
        assert listed.json()["data"]["items"] == []
        assert detail.status_code == 404

    def test_generate_commits_regenerated_schedule(self, api_client: TestClient, db_session, monkeypatch) -> None:
        ms, _rule, _v, _org, _early, _persons = self._setup_published_rule_with_schedule(db_session)
        _, token = _create_admin(api_client, db_session)
        committed = False
        original_commit = db_session.commit

        def track_commit() -> None:
            nonlocal committed
            committed = True
            original_commit()

        monkeypatch.setattr(db_session, "commit", track_commit)

        resp = api_client.post(
            f"/api/v1/schedules/{ms.id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert committed is True

    def test_generate_schedule_not_found(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T4: 排班不存在 404"""
        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            "/api/v1/schedules/99999/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_generate_rule_not_published(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T4: 规则未发布 422"""
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        _, token = _create_admin(api_client, db_session)
        resp = api_client.post(
            f"/api/v1/schedules/{ms.id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    def test_generate_requires_permission(self, api_client: TestClient, db_session) -> None:
        """M3-P1-T4: 无权限 403"""
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        early = _create_shift_def(db_session)
        p1 = _create_person(db_session, org, "P001", "张三")
        ms = _build_full_schedule(db_session, org, rule, [early], [p1])

        create_user(db_session, "nogen", "pass", "无权限")
        db_session.commit()
        token = _login(api_client, db_session, "nogen", "pass")
        resp = api_client.post(
            f"/api/v1/schedules/{ms.id}/generate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestScheduleCurrentRoom:
    def test_admin_requires_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session, select_room=False)

        resp = api_client.get("/api/v1/schedules", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 422
        assert resp.json()["code"] == "ADMIN_NO_ROOM_SELECTED"

    def test_list_ignores_client_org_unit_and_uses_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room_a = _create_org(db_session, "current-schedule-a", "机房A", "room")
        room_b = _create_org(db_session, "current-schedule-b", "机房B", "room")
        rule = _create_rule(db_session)
        person_a = _create_person(db_session, room_a, "CURRENT-SA")
        person_b = _create_person(db_session, room_b, "CURRENT-SB")
        _build_full_schedule(db_session, room_a, rule, [], [person_a])
        _build_full_schedule(db_session, room_b, rule, [], [person_b])

        resp = api_client.get(
            f"/api/v1/schedules?org_unit_id={room_b.id}",
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)},
        )

        assert resp.status_code == 200
        assert [item["org_unit_id"] for item in resp.json()["data"]["items"]] == [room_a.id]

    def test_detail_rejects_schedule_outside_current_room(self, api_client: TestClient, db_session) -> None:
        _, token = _create_admin(api_client, db_session)
        room_a = _create_org(db_session, "schedule-detail-a", "机房A", "room")
        room_b = _create_org(db_session, "schedule-detail-b", "机房B", "room")
        rule = _create_rule(db_session)
        person = _create_person(db_session, room_b, "OUTSIDE-SCHEDULE")
        schedule = _build_full_schedule(db_session, room_b, rule, [], [person])

        resp = api_client.get(
            f"/api/v1/schedules/{schedule.id}",
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)},
        )

        assert resp.status_code == 404

    @pytest.mark.parametrize("method,path_suffix", [
        ("get", "/days"),
        ("get", "/days/range?from=2026-07-01&to=2026-07-02"),
        ("post", "/generate"),
    ])
    def test_subresource_routes_reject_schedule_outside_current_room(
        self, api_client: TestClient, db_session, method: str, path_suffix: str,
    ) -> None:
        _, token = _create_admin(api_client, db_session)
        room_a = _create_org(db_session, f"schedule-route-a-{method}-{len(path_suffix)}", "机房A", "room")
        room_b = _create_org(db_session, f"schedule-route-b-{method}-{len(path_suffix)}", "机房B", "room")
        rule = _create_rule(db_session)
        person = _create_person(db_session, room_b, f"OUTSIDE-{method}-{len(path_suffix)}")
        schedule = _build_full_schedule(db_session, room_b, rule, [], [person])

        response = getattr(api_client, method)(
            f"/api/v1/schedules/{schedule.id}{path_suffix}",
            headers={"Authorization": f"Bearer {token}", "X-Current-Room-Id": str(room_a.id)},
        )

        assert response.status_code == 404
