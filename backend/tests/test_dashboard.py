from datetime import UTC, date, datetime, timedelta

import pytest
from app.models.approval import ApprovalTask
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import (
    CoverAssignment,
    LeaveRequest,
    MonthlySchedule,
    ScheduleDay,
    ScheduleShift,
    ScheduleShiftPerson,
    ShiftSwap,
)
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "password123"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _fixture(db):
    room = OrgUnit(code="DASH-ROOM", name="工作台机房", type="room")
    db.add(room)
    db.flush()
    operator = Person(code="DASH-OP", name="值机员", person_type="duty_operator", org_unit_id=room.id, participate_schedule=True)
    cover = Person(code="DASH-COVER", name="检修员", person_type="maintenance", org_unit_id=room.id)
    db.add_all((operator, cover))
    db.flush()
    operator_user = create_user(db, "dashboard-operator", "password123", "值机账号", operator.id)
    manager_user = create_user(db, "dashboard-manager", "password123", "管理账号", cover.id)
    permission = SysPermission(code="approval:task:view_todo", name="审批待办", type="api")
    cover_permission = SysPermission(code="cover:assignment:view", name="顶班安排", type="api")
    schedule_permission = SysPermission(code="schedule:monthly:view", name="查看排班", type="api")
    role = SysRole(code="dashboard-manager", name="工作台管理员")
    role.permissions.extend((permission, cover_permission, schedule_permission))
    manager_user.roles.append(role)
    shift_def = ShiftDef(org_unit_id=room.id, code="DASH-SHIFT", name="早班", start_time="00:00", end_time="08:00")
    today = date.today()
    rule = ShiftRule(org_unit_id=room.id, code="DASH-RULE", name="工作台规则", cycle_days=1, start_date=today.isoformat(), persons_per_cell=1)
    db.add_all((shift_def, rule))
    db.flush()
    version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date=today.isoformat(), persons_per_cell=1, snapshot={})
    db.add(version)
    db.flush()
    schedule = MonthlySchedule(org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id, status="published")
    db.add(schedule)
    db.flush()
    for duty_date in (today, today + timedelta(days=2)):
        day = ScheduleDay(schedule_id=schedule.id, duty_date=duty_date, weekday=duty_date.weekday())
        db.add(day)
        db.flush()
        shift = ScheduleShift(schedule_day_id=day.id, shift_def_id=shift_def.id, start_at=datetime.combine(duty_date, datetime.min.time(), UTC), end_at=datetime.combine(duty_date, datetime.min.time(), UTC) + timedelta(hours=8))
        db.add(shift)
        db.flush()
        db.add(ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=operator.id))
        if duty_date == today:
            today_shift = shift
    db.flush()
    db.add(ShiftSwap(biz_no="DASH-SWAP", swap_type="one_way", applicant_person_id=cover.id, source_shift_id=today_shift.id, target_person_id=operator.id, status="wait_target_confirm"))
    leave = LeaveRequest(biz_no="DASH-LEAVE", applicant_person_id=operator.id, schedule_shift_id=today_shift.id, leave_type="personal", status="pending_arrangement")
    db.add(leave)
    db.flush()
    db.add(CoverAssignment(biz_no="DASH-COVER", leave_request_id=leave.id, status="pending_arrangement"))
    db.add(ApprovalTask(org_unit_id=room.id, biz_type="leave_request", biz_id=leave.id, node_code="director_approval", assignee_user_id=manager_user.id, status="pending"))
    db.commit()
    return operator_user, manager_user


def test_dashboard_returns_personal_duties_and_confirmation_counts(api_client: TestClient, db_session):
    operator, _manager = _fixture(db_session)

    response = api_client.get("/api/v1/dashboard", headers=_login(api_client, operator.username))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["personal"]["today_duties"][0] == {"duty_date": date.today().isoformat(), "shift_name": "早班", "persons": ["值机员"]}
    assert data["personal"]["next_duty"]["duty_date"] == (date.today() + timedelta(days=2)).isoformat()
    assert data["personal"]["pending_swap_confirm_count"] == 1
    assert data["personal"]["pending_cover_confirm_count"] == 0
    assert data["management"] is None
    assert data["reminders"] == [{"type": "swap_confirm", "title": "待确认换班", "count": 1, "path": "/swap-request"}]


def test_dashboard_returns_management_counts_only_for_granted_permissions(api_client: TestClient, db_session):
    _operator, manager = _fixture(db_session)

    response = api_client.get("/api/v1/dashboard", headers=_login(api_client, manager.username))

    assert response.status_code == 200
    management = response.json()["data"]["management"]
    assert management["pending_approval_count"] == 1
    assert management["pending_cover_arrangement_count"] == 1
    assert management["schedule_status"] == "published"
    assert {item["type"] for item in response.json()["data"]["reminders"]} == {"approval", "cover_arrangement"}


def test_dashboard_management_cards_accept_direct_permissions(api_client: TestClient, db_session):
    _operator, manager = _fixture(db_session)
    permissions = list(manager.roles[0].permissions)
    manager.roles.clear()
    manager.direct_permissions.extend(permissions)
    db_session.commit()

    response = api_client.get("/api/v1/dashboard", headers=_login(api_client, manager.username))

    assert response.status_code == 200
    management = response.json()["data"]["management"]
    assert management["pending_approval_count"] == 1
    assert management["pending_cover_arrangement_count"] == 1
    assert management["schedule_status"] == "published"


def test_dashboard_requires_authentication(api_client: TestClient):
    response = api_client.get("/api/v1/dashboard")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_system_admin_must_select_room_and_dashboard_counts_do_not_cross_rooms(api_client: TestClient, db_session):
    _operator, manager = _fixture(db_session)
    manager.roles[0].code = "system_admin"
    other_room = OrgUnit(code="DASH-OTHER", name="其他工作台机房", type="room")
    db_session.add(other_room)
    db_session.flush()
    db_session.add_all((
        ApprovalTask(org_unit_id=other_room.id, biz_type="leave_request", biz_id=901, node_code="director_approval", assignee_user_id=manager.id, status="pending"),
        ApprovalTask(org_unit_id=other_room.id, biz_type="leave_request", biz_id=902, node_code="director_approval", assignee_user_id=manager.id, status="pending"),
    ))
    db_session.commit()
    headers = _login(api_client, manager.username)

    assert api_client.get("/api/v1/dashboard", headers=headers).status_code == 422
    original = api_client.get("/api/v1/dashboard", headers={**headers, "X-Current-Room-Id": str(manager.person_id and db_session.get(Person, manager.person_id).org_unit_id)})
    other = api_client.get("/api/v1/dashboard", headers={**headers, "X-Current-Room-Id": str(other_room.id)})

    assert original.status_code == 200
    assert original.json()["data"]["management"]["pending_approval_count"] == 1
    assert other.status_code == 200
    assert other.json()["data"]["management"]["pending_approval_count"] == 2
