from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.models.export import ExportTask
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user
from app.services.export import create_schedule_export
from fastapi.testclient import TestClient
from sqlalchemy import select

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(api_client: TestClient, username: str) -> str:
    response = api_client.post("/api/v1/auth/login", json={"username": username, "password": "password123"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _create_export_user(
    db_session, room: OrgUnit, username: str, *, can_export: bool = True, can_generate: bool = False
) -> str:
    person = Person(code=f"{username}-person", name=username, person_type="duty_operator", org_unit_id=room.id)
    db_session.add(person)
    db_session.flush()
    user = create_user(db_session, username, "password123", username, person_id=person.id)
    if can_export:
        permissions = [SysPermission(code="export:task:view", name="查看导出", type="api")]
        if can_generate:
            permissions.append(SysPermission(code="schedule:monthly:generate", name="生成排班", type="api"))
        role = SysRole(code=f"{username}-role", name=f"{username}角色")
        role.permissions.extend(permissions)
        user.roles.append(role)
        db_session.add_all([*permissions, role])
    db_session.add(user)
    db_session.commit()
    return username


def _create_published_schedule(db_session, room: OrgUnit, *, duty_date: date = date(2026, 7, 1)) -> MonthlySchedule:
    rule = ShiftRule(
        code=f"RULE-{room.id}", name="规则", org_unit_id=room.id, cycle_days=1,
        start_date=duty_date.isoformat(), persons_per_cell=1, status="published",
    )
    db_session.add(rule)
    db_session.flush()
    version = ShiftRuleVersion(
        rule_id=rule.id, version_no=1, cycle_days=1, start_date=duty_date.isoformat(),
        persons_per_cell=1, snapshot={}, status="published",
    )
    shift_def = ShiftDef(org_unit_id=room.id, code=f"day-{room.id}", name="白班", start_time="00:00", end_time="08:00")
    person = Person(code=f"DUTY-{room.id}", name="值班员", person_type="duty_operator", org_unit_id=room.id)
    db_session.add_all([version, shift_def, person])
    db_session.flush()
    schedule = MonthlySchedule(org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id, status="published")
    db_session.add(schedule)
    db_session.flush()
    day = ScheduleDay(schedule_id=schedule.id, duty_date=duty_date, weekday=duty_date.weekday())
    db_session.add(day)
    db_session.flush()
    shift = ScheduleShift(
        schedule_day_id=day.id, shift_def_id=shift_def.id,
        start_at=datetime.combine(duty_date, datetime.min.time(), UTC),
        end_at=datetime.combine(duty_date, datetime.min.time(), UTC),
    )
    db_session.add(shift)
    db_session.flush()
    db_session.add(ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=person.id, position_no=1))
    db_session.commit()
    return schedule


def test_schedule_export_writes_month_headers_and_staff(tmp_path: Path, db_session) -> None:
    room = OrgUnit(code="R001", name="发射机房", type="room", status="enabled")
    db_session.add(room)
    db_session.flush()
    rule = ShiftRule(
        code="RULE1",
        name="规则",
        org_unit_id=room.id,
        cycle_days=1,
        start_date="2026-07-01",
        persons_per_cell=1,
        status="published",
    )
    db_session.add(rule)
    db_session.flush()
    version = ShiftRuleVersion(
        rule_id=rule.id,
        version_no=1,
        cycle_days=1,
        start_date="2026-07-01",
        persons_per_cell=1,
        snapshot={},
        status="published",
    )
    early = ShiftDef(
        org_unit_id=room.id, code="early", name="早班", start_time="00:00", end_time="08:00", status="enabled"
    )
    person = Person(
        code="P001",
        name="张三",
        org_unit_id=room.id,
        person_type="operator",
        status="enabled",
        participate_schedule=True,
    )
    db_session.add_all([version, early, person])
    db_session.flush()
    schedule = MonthlySchedule(org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id, status="published")
    db_session.add(schedule)
    db_session.flush()
    day = ScheduleDay(schedule_id=schedule.id, duty_date=date(2026, 7, 1), weekday=2)
    db_session.add(day)
    db_session.flush()
    shift = ScheduleShift(
        schedule_day_id=day.id,
        shift_def_id=early.id,
        start_at=datetime(2026, 7, 1, tzinfo=UTC),
        end_at=datetime(2026, 7, 1, 8, tzinfo=UTC),
    )
    db_session.add(shift)
    db_session.flush()
    db_session.add(ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=person.id, position_no=1))
    db_session.commit()

    task = ExportTask(org_unit_id=room.id, task_type="schedule", status="pending", year_month="2026-07")
    db_session.add(task)
    db_session.flush()
    result = create_schedule_export(db_session, task, schedule, 2026, 7, tmp_path)

    assert result.status == "completed"
    assert result.file_path is not None
    assert (tmp_path / result.file_path).is_file()
    # XLSX is a zip package; shared strings contain the required headers and data.
    import zipfile

    with zipfile.ZipFile(tmp_path / result.file_path) as workbook:
        contents = b"".join(workbook.read(name) for name in workbook.namelist())
    assert "日期".encode() in contents
    assert "星期".encode() in contents
    assert "早班".encode() in contents
    assert "张三".encode() in contents


def test_export_api_creates_lists_and_downloads_file(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="EXPORT-ROOM", name="导出机房", type="room")
    db_session.add(room)
    db_session.commit()
    schedule = _create_published_schedule(db_session, room)
    username = _create_export_user(db_session, room, "exporter", can_generate=True)
    headers = {"Authorization": f"Bearer {_login(api_client, username)}"}

    created = api_client.post(
        "/api/v1/exports/schedule", json={"schedule_id": schedule.id, "year": 2026, "month": 7}, headers=headers
    )
    assert created.status_code == 200
    task_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "completed"

    listed = api_client.get("/api/v1/exports", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    downloaded = api_client.get(f"/api/v1/exports/{task_id}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    assert downloaded.content[:2] == b"PK"


def test_export_api_rejects_month_without_schedule_data(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="EMPTY-ROOM", name="空机房", type="room")
    db_session.add(room)
    db_session.commit()
    schedule = _create_published_schedule(db_session, room)
    username = _create_export_user(db_session, room, "empty-exporter", can_generate=True)

    response = api_client.post(
        "/api/v1/exports/schedule", json={"schedule_id": schedule.id, "year": 2026, "month": 8},
        headers={"Authorization": f"Bearer {_login(api_client, username)}"},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "该月份暂无排班数据"
    assert db_session.scalar(select(ExportTask.status)) == "failed"


def test_export_api_requires_schedule_management_permission(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="PERMISSION-ROOM", name="权限机房", type="room")
    db_session.add(room)
    db_session.commit()
    schedule = _create_published_schedule(db_session, room)
    username = _create_export_user(db_session, room, "history-only")

    response = api_client.post(
        "/api/v1/exports/schedule", json={"schedule_id": schedule.id, "year": 2026, "month": 7},
        headers={"Authorization": f"Bearer {_login(api_client, username)}"},
    )
    assert response.status_code == 403


def test_download_hides_other_room_task_and_rejects_missing_file(api_client: TestClient, db_session) -> None:
    first_room = OrgUnit(code="FIRST-ROOM", name="第一机房", type="room")
    second_room = OrgUnit(code="SECOND-ROOM", name="第二机房", type="room")
    db_session.add_all([first_room, second_room])
    db_session.flush()
    task = ExportTask(
        org_unit_id=first_room.id, task_type="schedule", status="completed", year_month="2026-07",
        file_name="missing.xlsx", file_path="missing.xlsx",
    )
    db_session.add(task)
    db_session.commit()
    username = _create_export_user(db_session, second_room, "second-exporter")
    headers = {"Authorization": f"Bearer {_login(api_client, username)}"}

    assert api_client.get(f"/api/v1/exports/{task.id}/download", headers=headers).status_code == 404
    own_task = ExportTask(
        org_unit_id=second_room.id, task_type="schedule", status="completed", year_month="2026-07",
        file_name="missing.xlsx", file_path="missing.xlsx",
    )
    db_session.add(own_task)
    db_session.commit()
    assert api_client.get(f"/api/v1/exports/{own_task.id}/download", headers=headers).status_code == 404

    traversal_task = ExportTask(
        org_unit_id=second_room.id, task_type="schedule", status="completed", year_month="2026-07",
        file_name="outside.xlsx", file_path="../outside.xlsx",
    )
    db_session.add(traversal_task)
    db_session.commit()
    assert api_client.get(f"/api/v1/exports/{traversal_task.id}/download", headers=headers).status_code == 404
