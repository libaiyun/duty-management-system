from datetime import UTC, date, datetime, timedelta

import pytest
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysPermission, SysRole
from app.services.auth import check_user_permission, create_user, seed_permission_system
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(client: TestClient, username: str, password: str = "password123") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_effective_permission_is_role_union_direct_grant_and_superuser_bypass(db_session) -> None:
    role_permission = SysPermission(code="test:role", name="角色权限", type="api", group_code="test")
    direct_permission = SysPermission(code="test:direct", name="直接权限", type="api", group_code="test")
    role = SysRole(code="tester", name="测试角色")
    role.permissions.append(role_permission)
    user = create_user(db_session, "normal", "password123", "普通账号")
    user.roles.append(role)
    user.direct_permissions.append(direct_permission)
    superuser = create_user(db_session, "root", "password123", "超级管理员", is_superuser=True)
    db_session.add_all([role_permission, direct_permission, role])
    db_session.flush()

    assert check_user_permission(db_session, user, "test:role")
    assert check_user_permission(db_session, user, "test:direct")
    assert check_user_permission(db_session, superuser, "permission:not-registered")


def test_disabled_role_and_permission_do_not_grant_access(db_session) -> None:
    disabled_permission = SysPermission(
        code="test:disabled-permission", name="停用权限", type="api",
        group_code="test", status="disabled",
    )
    enabled_permission = SysPermission(
        code="test:disabled-role", name="停用角色权限", type="api", group_code="test",
    )
    disabled_role = SysRole(code="disabled-role", name="停用角色", status="disabled")
    disabled_role.permissions.extend([disabled_permission, enabled_permission])
    user = create_user(db_session, "disabled-grants", "password123", "停用授权")
    user.roles.append(disabled_role)
    db_session.add_all([disabled_permission, enabled_permission, disabled_role])
    db_session.flush()

    assert not check_user_permission(db_session, user, "test:disabled-permission")
    assert not check_user_permission(db_session, user, "test:disabled-role")


def test_reseeding_does_not_restore_removed_system_admin_grant(db_session) -> None:
    seed_permission_system(db_session)
    role = db_session.query(SysRole).filter_by(code="system_admin").one()
    removed = role.permissions[0]
    role.permissions.remove(removed)
    db_session.flush()

    seed_permission_system(db_session)

    assert removed not in role.permissions


def test_account_detail_exposes_effective_permissions_and_sources(api_client: TestClient, db_session) -> None:
    manage = SysPermission(code="system:user:manage", name="账号管理", type="api", group_code="system")
    role_permission = SysPermission(code="test:role", name="角色权限", type="api", group_code="test")
    direct_permission = SysPermission(code="test:direct", name="直接权限", type="api", group_code="test")
    create_user(db_session, "manager", "password123", "管理员", is_superuser=True)
    target = create_user(db_session, "target", "password123", "目标账号")
    role = SysRole(code="tester", name="测试角色")
    role.permissions.extend([manage, role_permission])
    target.roles.append(role)
    target.direct_permissions.append(direct_permission)
    db_session.add_all([manage, role_permission, direct_permission, role])
    db_session.commit()

    response = api_client.get(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {_login(api_client, 'manager')}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data["effective_permission_codes"]) == {"system:user:manage", "test:role", "test:direct"}
    assert data["permission_sources"]["test:direct"] == ["direct"]
    assert data["permission_sources"]["test:role"] == ["role:tester"]


def test_normal_account_room_is_fixed_by_bound_person(api_client: TestClient, db_session) -> None:
    permission = SysPermission(code="schedule:monthly:view", name="查看排班", type="api", group_code="schedule")
    role = SysRole(code="viewer", name="查看者")
    role.permissions.append(permission)
    room = OrgUnit(code="room-fixed", name="固定机房", type="room")
    db_session.add_all([permission, role, room])
    db_session.flush()
    person = Person(code="P-FIXED", name="固定人员", person_type="duty_operator", org_unit_id=room.id)
    db_session.add(person)
    db_session.flush()
    user = create_user(db_session, "viewer", "password123", "查看者", person_id=person.id)
    user.roles.append(role)
    db_session.commit()

    response = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {_login(api_client, 'viewer')}", "X-Current-Room-Id": "999999"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["room_id"] == room.id
    assert response.json()["data"]["can_switch_room"] is False


def test_disabled_bound_person_cannot_use_personal_business_api(
    api_client: TestClient, db_session,
) -> None:
    room = OrgUnit(code="disabled-person-room", name="停用人员机房", type="room")
    db_session.add(room)
    db_session.flush()
    person = Person(
        code="DISABLED-PERSON", name="停用人员", person_type="duty_operator",
        org_unit_id=room.id, status="disabled",
    )
    db_session.add(person)
    db_session.flush()
    create_user(db_session, "disabled-person", "password123", "停用人员", person_id=person.id)
    db_session.commit()

    response = api_client.get(
        "/api/v1/shift-swaps",
        headers={"Authorization": f"Bearer {_login(api_client, 'disabled-person')}"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "BUSINESS_RULE_FAILED"


def test_normal_manager_bound_outside_room_cannot_use_room_business_api(
    api_client: TestClient, db_session,
) -> None:
    station = OrgUnit(code="station-bound", name="台站", type="station")
    permission = SysPermission(code="person:manage:view", name="人员管理", type="api", group_code="person")
    role = SysRole(code="station-person-manager", name="人员管理员")
    role.permissions.append(permission)
    db_session.add_all([station, permission, role])
    db_session.flush()
    person = Person(
        code="STATION-BOUND", name="台站人员", person_type="room_director",
        org_unit_id=station.id,
    )
    db_session.add(person)
    db_session.flush()
    user = create_user(db_session, "station-bound", "password123", "台站人员", person_id=person.id)
    user.roles.append(role)
    db_session.commit()

    response = api_client.get(
        "/api/v1/persons",
        headers={"Authorization": f"Bearer {_login(api_client, 'station-bound')}"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "BUSINESS_RULE_FAILED"


def test_room_switching_account_cannot_select_disabled_room(
    api_client: TestClient, db_session,
) -> None:
    room = OrgUnit(code="disabled-room", name="已停用机房", type="room", status="disabled")
    db_session.add(room)
    create_user(db_session, "room-root", "password123", "超级管理员", is_superuser=True)
    db_session.commit()

    response = api_client.get(
        "/api/v1/persons",
        headers={
            "Authorization": f"Bearer {_login(api_client, 'room-root')}",
            "X-Current-Room-Id": str(room.id),
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "BUSINESS_RULE_FAILED"


def test_personal_swap_page_does_not_require_function_permission(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="personal-room", name="个人机房", type="room")
    db_session.add(room)
    db_session.flush()
    person = Person(code="PERSONAL", name="个人", person_type="duty_operator", org_unit_id=room.id)
    db_session.add(person)
    db_session.flush()
    create_user(db_session, "personal", "password123", "个人", person_id=person.id)
    db_session.commit()

    response = api_client.get(
        "/api/v1/shift-swaps",
        headers={"Authorization": f"Bearer {_login(api_client, 'personal')}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []


def test_normal_manager_cannot_modify_superuser(api_client: TestClient, db_session) -> None:
    permission = SysPermission(
        code="system:user:manage", name="账号管理", type="api", group_code="system",
    )
    role = SysRole(code="account-manager", name="账号管理员")
    role.permissions.append(permission)
    manager = create_user(db_session, "account-manager", "password123", "账号管理员")
    manager.roles.append(role)
    superuser = create_user(db_session, "protected-root", "password123", "超级管理员", is_superuser=True)
    db_session.add_all([permission, role])
    db_session.commit()
    headers = {"Authorization": f"Bearer {_login(api_client, 'account-manager')}"}

    disable = api_client.put(f"/api/v1/users/{superuser.id}", json={"status": "disabled"}, headers=headers)
    reset_password = api_client.post(
        "/api/v1/auth/password/reset",
        json={"user_id": superuser.id, "new_password": "new-password"},
        headers=headers,
    )
    roles = api_client.put(
        f"/api/v1/users/{superuser.id}/roles", json={"role_ids": []}, headers=headers,
    )
    permissions = api_client.put(
        f"/api/v1/users/{superuser.id}/permissions", json={"permission_ids": []}, headers=headers,
    )

    assert disable.status_code == 403
    assert reset_password.status_code == 403
    assert roles.status_code == 403
    assert permissions.status_code == 403


def test_bound_person_without_function_permission_can_only_read_own_published_schedule(
    api_client: TestClient, db_session,
) -> None:
    room = OrgUnit(code="personal-schedule-room", name="个人排班机房", type="room")
    db_session.add(room)
    db_session.flush()
    own_person = Person(
        code="OWN-SCHEDULE", name="本人", person_type="duty_operator",
        org_unit_id=room.id, participate_schedule=True,
    )
    other_person = Person(
        code="OTHER-SCHEDULE", name="他人", person_type="duty_operator",
        org_unit_id=room.id, participate_schedule=True,
    )
    db_session.add_all([own_person, other_person])
    db_session.flush()
    create_user(db_session, "personal-schedule", "password123", "本人", person_id=own_person.id)
    shift_def = ShiftDef(
        org_unit_id=room.id, code="personal-shift", name="早班",
        start_time="00:00", end_time="08:00",
    )
    rule = ShiftRule(
        org_unit_id=room.id, code="personal-rule", name="个人排班规则",
        cycle_days=1, start_date=date.today().isoformat(), persons_per_cell=1,
    )
    db_session.add_all([shift_def, rule])
    db_session.flush()
    version = ShiftRuleVersion(
        rule_id=rule.id, version_no=1, cycle_days=1,
        start_date=date.today().isoformat(), persons_per_cell=1, snapshot={},
    )
    db_session.add(version)
    db_session.flush()
    schedule = MonthlySchedule(
        org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id,
        status="published",
    )
    db_session.add(schedule)
    db_session.flush()
    for offset, person in enumerate((own_person, other_person)):
        duty_date = date.today() + timedelta(days=offset)
        day = ScheduleDay(
            schedule_id=schedule.id, duty_date=duty_date,
            weekday=duty_date.weekday(), is_legal_holiday=False,
        )
        db_session.add(day)
        db_session.flush()
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=datetime.combine(duty_date, datetime.min.time(), UTC),
            end_at=datetime.combine(duty_date, datetime.min.time(), UTC) + timedelta(hours=8),
        )
        db_session.add(shift)
        db_session.flush()
        db_session.add(ScheduleShiftPerson(
            schedule_shift_id=shift.id, person_id=person.id, position_no=1,
        ))
    db_session.commit()
    headers = {"Authorization": f"Bearer {_login(api_client, 'personal-schedule')}"}

    listing = api_client.get("/api/v1/schedules", headers=headers)
    days = api_client.get(f"/api/v1/schedules/{schedule.id}/days", headers=headers)

    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()["data"]["items"]] == [schedule.id]
    assert days.status_code == 200
    returned_days = days.json()["data"]
    assert len(returned_days) == 1
    assert returned_days[0]["shifts"][0]["persons"][0]["person_id"] == own_person.id
