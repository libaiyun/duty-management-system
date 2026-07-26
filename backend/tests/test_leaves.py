from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.core.exceptions import BusinessRuleError, ForbiddenError
from app.models.approval import ApprovalTask
from app.models.holiday import HolidayCalendar
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import (
    CoverAssignment,
    DutyChangeLedger,
    LeaveRequest,
    MonthlySchedule,
    ScheduleDay,
    ScheduleShift,
    ScheduleShiftPerson,
)
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user
from app.services.leave import (
    arrange_cover,
    cancel_cover,
    confirm_cover,
    create_leave,
    decide_leave,
    get_cover,
    withdraw_leave,
)
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "password123"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _fixture(db):
    room = OrgUnit(code="LEAVE-ROOM", name="请假机房", type="room")
    db.add(room)
    db.flush()
    operator = Person(code="LEAVE-OP", name="值机员", person_type="duty_operator", org_unit_id=room.id, participate_schedule=True)
    cover = Person(code="LEAVE-MT", name="检修员", person_type="maintenance", org_unit_id=room.id)
    director = Person(code="LEAVE-DR", name="主任", person_type="room_director", org_unit_id=room.id)
    db.add_all((operator, cover, director))
    db.flush()
    operator_user = create_user(db, "leave-operator", "password123", "值机账号", operator.id)
    cover_user = create_user(db, "leave-cover", "password123", "检修账号", cover.id)
    director_user = create_user(db, "leave-director", "password123", "主任账号", director.id)
    role = SysRole(code="leave-approval", name="请假审批")
    role.permissions.append(SysPermission(code="approval:task:view_todo", name="处理审批", type="api"))
    director_user.roles.append(role)
    definition = ShiftDef(org_unit_id=room.id, code="leave-shift", name="早班", start_time="00:00", end_time="08:00")
    start = date.today() + timedelta(days=2)
    rule = ShiftRule(org_unit_id=room.id, code="leave-rule", name="请假规则", cycle_days=1, start_date=start.isoformat(), persons_per_cell=1)
    db.add_all((definition, rule))
    db.flush()
    version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date=start.isoformat(), persons_per_cell=1, snapshot={})
    db.add(version)
    db.flush()
    schedule = MonthlySchedule(org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id, status="published")
    db.add(schedule)
    db.flush()
    day = ScheduleDay(schedule_id=schedule.id, duty_date=start, weekday=start.weekday())
    db.add(day)
    db.flush()
    shift = ScheduleShift(schedule_day_id=day.id, shift_def_id=definition.id, start_at=datetime.combine(start, datetime.min.time(), UTC), end_at=datetime.combine(start, datetime.min.time(), UTC) + timedelta(hours=8))
    db.add(shift)
    db.flush()
    db.add(ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=operator.id))
    db.commit()
    return room, operator_user, cover_user, director_user, operator, cover, shift


def test_approved_leave_creates_pending_cover_and_confirm_updates_final_duty(db_session):
    room, applicant, cover_user, director, _operator, cover_person, shift = _fixture(db_session)
    leave = create_leave(db_session, SimpleNamespace(schedule_shift_id=shift.id, leave_type="personal", reason="事假"), applicant, room.id)
    decide_leave(db_session, leave.id, director, approve=True)
    cover = db_session.scalar(select(CoverAssignment).where(CoverAssignment.leave_request_id == leave.id))
    assert cover is not None and cover.status == "pending_arrangement"
    arrange_cover(db_session, cover.id, cover_person.id, "顶班", director, room.id)
    confirm_cover(db_session, cover.id, cover_user, approve=True, opinion=None, room_id=room.id)
    assert db_session.get(LeaveRequest, leave.id).status == "completed"
    assert get_cover(db_session, cover.id).status == "effective"
    assert db_session.scalar(select(ScheduleShiftPerson.person_id).where(ScheduleShiftPerson.schedule_shift_id == shift.id)) == cover_person.id
    assert db_session.scalar(select(DutyChangeLedger).where(DutyChangeLedger.change_type == "leave_cover")) is not None


def test_legal_holiday_leave_is_rejected(db_session):
    room, applicant, _cover_user, _director, _operator, _cover_person, shift = _fixture(db_session)
    db_session.add(HolidayCalendar(holiday_date=shift.schedule_day.duty_date, holiday_name="节日", year=shift.schedule_day.duty_date.year, is_legal=True, status="enabled"))
    db_session.flush()
    with pytest.raises(BusinessRuleError, match="法定节假日"):
        create_leave(db_session, SimpleNamespace(schedule_shift_id=shift.id, leave_type="public", reason=None), applicant, room.id)


def test_eligible_leave_shifts_excludes_a_legal_holiday_added_after_schedule_generation(api_client: TestClient, db_session):
    room, applicant, _cover_user, _director, _operator, _cover_person, shift = _fixture(db_session)
    # The schedule-day flag is a generation-time snapshot.  The request page
    # must also honour the current holiday calendar used by the submit API.
    db_session.add(HolidayCalendar(
        holiday_date=shift.schedule_day.duty_date,
        holiday_name="新增法定节假日",
        year=shift.schedule_day.duty_date.year,
        is_legal=True,
        status="enabled",
    ))
    db_session.commit()

    response = api_client.get("/api/v1/leaves/eligible-shifts", headers=_login(api_client, applicant.username))

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_only_applicant_can_withdraw_pending_leave(db_session):
    room, applicant, cover_user, _director, _operator, _cover_person, shift = _fixture(db_session)
    leave = create_leave(db_session, SimpleNamespace(schedule_shift_id=shift.id, leave_type="sick", reason=None), applicant, room.id)
    with pytest.raises(ForbiddenError, match="仅申请人"):
        withdraw_leave(db_session, leave.id, cover_user, room.id)


def test_withdrawing_leave_cancels_its_pending_approval_task(db_session):
    room, applicant, _cover_user, _director, _operator, _cover_person, shift = _fixture(db_session)
    leave = create_leave(
        db_session,
        SimpleNamespace(schedule_shift_id=shift.id, leave_type="personal", reason=None),
        applicant,
        room.id,
    )

    withdraw_leave(db_session, leave.id, applicant, room.id)

    task = db_session.scalar(select(ApprovalTask).where(
        ApprovalTask.biz_type == "leave_request", ApprovalTask.biz_id == leave.id,
    ))
    assert task is not None
    assert task.status == "cancelled"


def test_cover_rejection_returns_leave_to_pending_arrangement(db_session):
    room, applicant, cover_user, director, _operator, cover_person, shift = _fixture(db_session)
    leave = create_leave(db_session, SimpleNamespace(schedule_shift_id=shift.id, leave_type="personal", reason=None), applicant, room.id)
    decide_leave(db_session, leave.id, director, approve=True)
    cover = db_session.scalar(select(CoverAssignment).where(CoverAssignment.leave_request_id == leave.id))
    assert cover is not None
    arrange_cover(db_session, cover.id, cover_person.id, None, director, room.id)
    confirm_cover(db_session, cover.id, cover_user, approve=False, opinion="不能顶班", room_id=room.id)
    assert get_cover(db_session, cover.id).status == "rearrange"
    assert db_session.get(LeaveRequest, leave.id).status == "pending_arrangement"


def test_leave_api_creates_personal_request_and_approval_generates_cover(api_client: TestClient, db_session):
    room, applicant, _cover_user, director, _operator, _cover_person, shift = _fixture(db_session)
    applicant_headers = _login(api_client, applicant.username)
    eligible = api_client.get("/api/v1/leaves/eligible-shifts", headers=applicant_headers)
    assert eligible.status_code == 200
    assert eligible.json()["data"][0]["id"] == shift.id
    created = api_client.post(
        "/api/v1/leaves",
        json={"schedule_shift_id": shift.id, "leave_type": "personal", "reason": "事假"},
        headers=applicant_headers,
    )
    assert created.status_code == 200
    assert api_client.get("/api/v1/leaves?view=mine", headers=applicant_headers).json()["data"]["total"] == 1
    task = db_session.scalar(select(ApprovalTask).where(ApprovalTask.biz_id == created.json()["data"]["id"]))
    assert task is not None
    approved = api_client.post(
        f"/api/v1/approval-tasks/{task.id}/approve",
        json={"opinion": "同意"},
        headers=_login(api_client, director.username),
    )
    assert approved.status_code == 200
    assert db_session.scalar(select(CoverAssignment).where(CoverAssignment.leave_request_id == created.json()["data"]["id"])) is not None


def test_effective_cover_can_be_voided_and_restores_original_duty_operator(db_session):
    room, applicant, cover_user, director, operator, cover_person, shift = _fixture(db_session)
    leave = create_leave(db_session, SimpleNamespace(schedule_shift_id=shift.id, leave_type="personal", reason=None), applicant, room.id)
    decide_leave(db_session, leave.id, director, approve=True)
    cover = db_session.scalar(select(CoverAssignment).where(CoverAssignment.leave_request_id == leave.id))
    assert cover is not None
    arrange_cover(db_session, cover.id, cover_person.id, None, director, room.id)
    confirm_cover(db_session, cover.id, cover_user, approve=True, opinion=None, room_id=room.id)
    cancel_cover(db_session, cover.id, "恢复原值机员", director, room.id)
    assert get_cover(db_session, cover.id).status == "cancelled"
    assert db_session.scalar(select(ScheduleShiftPerson.person_id).where(ScheduleShiftPerson.schedule_shift_id == shift.id)) == operator.id
