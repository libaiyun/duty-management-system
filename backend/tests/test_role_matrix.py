from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.role_matrix import CANONICAL_ROLE_CODES
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysDataScope, SysRole
from app.services.auth import create_user, seed_role_matrix


pytestmark = pytest.mark.usefixtures("create_tables")


def _token(api_client: TestClient, username: str) -> str:
    response = api_client.post("/api/v1/auth/login", json={"username": username, "password": "password123"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_seed_role_matrix_is_idempotent_and_replaces_legacy_grants(db_session) -> None:
    seed_role_matrix(db_session)
    seed_role_matrix(db_session)

    roles = db_session.query(SysRole).all()
    assert {role.code for role in roles} == CANONICAL_ROLE_CODES
    director = next(role for role in roles if role.code == "room_director")
    deputy = next(role for role in roles if role.code == "deputy_director")
    assert {permission.code for permission in director.permissions} == {permission.code for permission in deputy.permissions}
    assert sorted(scope.scope_type for scope in db_session.query(SysDataScope).all()) == [
        "all", "room", "room", "room", "room", "self", "self",
    ]


def test_role_mutations_and_user_scope_assignment_are_unavailable(api_client: TestClient, db_session) -> None:
    seed_role_matrix(db_session)
    admin = create_user(db_session, "admin", "password123", "管理员")
    admin.roles.append(db_session.query(SysRole).filter_by(code="system_admin").one())
    db_session.commit()
    token = _token(api_client, "admin")

    assert api_client.post("/api/v1/roles", json={"code": "custom", "name": "自定义"}, headers={"Authorization": f"Bearer {token}"}).status_code == 403
    role_id = db_session.query(SysRole).filter_by(code="duty_operator").one().id
    assert api_client.put(f"/api/v1/roles/{role_id}/permissions", json={"permission_ids": []}, headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert api_client.put(f"/api/v1/users/{admin.id}/data-scopes", json={"scopes": []}, headers={"Authorization": f"Bearer {token}"}).status_code == 404


def test_duty_operator_schedule_days_include_the_full_room_roster(api_client: TestClient, db_session) -> None:
    seed_role_matrix(db_session)
    room = OrgUnit(code="room", name="机房", type="room")
    db_session.add(room)
    db_session.flush()
    me = Person(code="ME", name="本人", person_type="duty_operator", org_unit_id=room.id)
    other = Person(code="OTHER", name="他人", person_type="duty_operator", org_unit_id=room.id)
    shift_def = ShiftDef(org_unit_id=room.id, code="day", name="白班", start_time="00:00", end_time="08:00")
    rule = ShiftRule(code="matrix-rule", name="规则", cycle_days=1, start_date="2026-08-01", persons_per_cell=2, org_unit_id=room.id)
    db_session.add_all([me, other, shift_def, rule])
    db_session.flush()
    version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date="2026-08-01", persons_per_cell=2, snapshot={"days": []})
    db_session.add(version)
    db_session.flush()
    schedule = MonthlySchedule(org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id, status="published")
    db_session.add(schedule)
    db_session.flush()
    day = ScheduleDay(schedule_id=schedule.id, duty_date=date(2026, 8, 1), weekday=5)
    db_session.add(day)
    db_session.flush()
    shift = ScheduleShift(schedule_day_id=day.id, shift_def_id=shift_def.id, start_at=datetime(2026, 8, 1, tzinfo=UTC), end_at=datetime(2026, 8, 1, 8, tzinfo=UTC), status="normal")
    db_session.add(shift)
    db_session.flush()
    db_session.add_all([ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=me.id, position_no=1, source_type="auto"), ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=other.id, position_no=2, source_type="auto")])
    user = create_user(db_session, "operator", "password123", "本人", person_id=me.id)
    user.roles.append(db_session.query(SysRole).filter_by(code="duty_operator").one())
    db_session.commit()

    response = api_client.get(f"/api/v1/schedules/{schedule.id}/days", headers={"Authorization": f"Bearer {_token(api_client, 'operator')}"})

    assert response.status_code == 200
    assert [person["person_id"] for person in response.json()["data"][0]["shifts"][0]["persons"]] == [me.id, other.id]
