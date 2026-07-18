import pytest
from app.core.exceptions import StateConflictError
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.user import SysPermission, SysRole
from app.services.approval import complete_task, create_task
from app.services.auth import create_user
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("create_tables")


def _login(client: TestClient, username: str) -> str:
    return client.post("/api/v1/auth/login", json={"username": username, "password": "password123"}).json()["data"]["access_token"]


def _user(db_session, room: OrgUnit, username: str, *permissions: str):
    person = Person(code=f"{username}-p", name=username, person_type="duty_operator", org_unit_id=room.id)
    db_session.add(person)
    db_session.flush()
    user = create_user(db_session, username, "password123", username, person.id)
    grants = []
    for code in permissions:
        permission = db_session.query(SysPermission).filter_by(code=code).one_or_none()
        grants.append(permission or SysPermission(code=code, name=code, type="api"))
    role = SysRole(code=f"{username}-role", name=f"{username}角色")
    role.permissions.extend(grants)
    user.roles.append(role)
    db_session.add_all([role, user])
    db_session.commit()
    return user


def test_create_and_complete_task_records_snapshot_and_prevents_repeat(db_session) -> None:
    room = OrgUnit(code="APPROVAL-ROOM", name="审批机房", type="room")
    db_session.add(room)
    db_session.flush()
    user = _user(db_session, room, "approver", "approval:task:view_todo", "approval:record:view_done")

    task = create_task(db_session, biz_type="leave_request", biz_id=7, node_code="director_approval", assignee_user_id=user.id, org_unit_id=room.id, snapshot={"applicant": "张三"})
    record = complete_task(db_session, task.id, user.id, action="approve", opinion="同意", snapshot={"status": "approved"})

    assert task.status == "approved"
    assert record.snapshot_json == {"status": "approved"}
    with pytest.raises(StateConflictError):
        complete_task(db_session, task.id, user.id, action="approve", opinion=None, snapshot={})


def test_todo_and_done_are_scoped_to_handler_and_room(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="APPROVAL-ROOM-API", name="审批机房", type="room")
    other_room = OrgUnit(code="APPROVAL-OTHER", name="其他机房", type="room")
    db_session.add_all([room, other_room])
    db_session.flush()
    user = _user(db_session, room, "approval-api", "approval:task:view_todo", "approval:record:view_done")
    other = _user(db_session, other_room, "approval-other", "approval:task:view_todo", "approval:record:view_done")
    mine = create_task(db_session, biz_type="shift_swap", biz_id=1, node_code="director_approval", assignee_user_id=user.id, org_unit_id=room.id, snapshot={})
    create_task(db_session, biz_type="leave_request", biz_id=2, node_code="director_approval", assignee_user_id=other.id, org_unit_id=other_room.id, snapshot={})
    db_session.commit()
    headers = {"Authorization": f"Bearer {_login(api_client, 'approval-api')}"}

    todo = api_client.get("/api/v1/approval-tasks/todo", headers=headers)
    assert todo.status_code == 200
    assert [item["id"] for item in todo.json()["data"]["items"]] == [mine.id]
    assert api_client.post(f"/api/v1/approval-tasks/{mine.id}/approve", json={"opinion": "通过"}, headers=headers).status_code == 200
    done = api_client.get("/api/v1/approval-tasks/done", headers=headers)
    assert done.status_code == 200
    assert done.json()["data"]["items"][0]["status"] == "approved"


def test_director_tasks_are_visible_and_actionable_by_another_approver_in_the_same_room(
    api_client: TestClient, db_session,
) -> None:
    room = OrgUnit(code="DIRECTOR-QUEUE", name="主任审批机房", type="room")
    db_session.add(room)
    db_session.flush()
    assignee = _user(db_session, room, "director-assignee", "approval:task:view_todo")
    _user(db_session, room, "deputy-peer", "approval:task:view_todo", "approval:record:view_done")
    task = create_task(
        db_session, biz_type="leave_request", biz_id=3, node_code="director_approval",
        assignee_user_id=assignee.id, org_unit_id=room.id, snapshot={},
    )
    db_session.commit()
    headers = {"Authorization": f"Bearer {_login(api_client, 'deputy-peer')}"}

    assert api_client.get("/api/v1/approval-tasks/todo", headers=headers).json()["data"]["items"][0]["id"] == task.id
    assert api_client.post(f"/api/v1/approval-tasks/{task.id}/approve", json={}, headers=headers).status_code == 200


def test_rejection_requires_opinion_and_non_assignee_cannot_handle_personal_task(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="PERSONAL-QUEUE", name="个人待办机房", type="room")
    db_session.add(room)
    db_session.flush()
    assignee = _user(db_session, room, "personal-assignee", "approval:task:view_todo")
    _user(db_session, room, "personal-peer", "approval:task:view_todo")
    task = create_task(
        db_session, biz_type="cover_assignment", biz_id=4, node_code="cover_confirm",
        assignee_user_id=assignee.id, org_unit_id=room.id, snapshot={},
    )
    db_session.commit()
    peer_headers = {"Authorization": f"Bearer {_login(api_client, 'personal-peer')}"}
    own_headers = {"Authorization": f"Bearer {_login(api_client, 'personal-assignee')}"}

    assert api_client.post(f"/api/v1/approval-tasks/{task.id}/approve", json={}, headers=peer_headers).status_code == 403
    rejected = api_client.post(f"/api/v1/approval-tasks/{task.id}/reject", json={}, headers=own_headers)
    assert rejected.status_code == 422
    assert rejected.json()["message"] == "拒绝时必须填写审批意见"


def test_approval_action_carries_forward_business_snapshot_and_records_are_queryable(
    api_client: TestClient, db_session,
) -> None:
    room = OrgUnit(code="SNAPSHOT-ROOM", name="快照机房", type="room")
    db_session.add(room)
    db_session.flush()
    user = _user(db_session, room, "snapshot-user", "approval:task:view_todo", "approval:record:view_done")
    task = create_task(
        db_session, biz_type="leave_request", biz_id=5, node_code="director_approval",
        assignee_user_id=user.id, org_unit_id=room.id,
        snapshot={"applicant_name": "张三", "duty_date": "2026-07-18", "summary": "事假"},
    )
    db_session.commit()
    headers = {"Authorization": f"Bearer {_login(api_client, 'snapshot-user')}"}

    assert api_client.post(f"/api/v1/approval-tasks/{task.id}/approve", json={"opinion": "同意"}, headers=headers).status_code == 200
    records = api_client.get("/api/v1/approval-records?biz_type=leave_request", headers=headers)
    assert records.status_code == 200
    assert records.json()["data"]["items"][-1]["snapshot"]["applicant_name"] == "张三"


def test_todo_api_filters_by_business_type_and_arrived_date(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="FILTER-ROOM", name="筛选机房", type="room")
    db_session.add(room)
    db_session.flush()
    user = _user(db_session, room, "filter-user", "approval:task:view_todo")
    create_task(db_session, biz_type="shift_swap", biz_id=6, node_code="director_approval", assignee_user_id=user.id, org_unit_id=room.id, snapshot={"applicant_name": "张三"})
    create_task(db_session, biz_type="leave_request", biz_id=7, node_code="director_approval", assignee_user_id=user.id, org_unit_id=room.id, snapshot={"applicant_name": "李四"})
    db_session.commit()
    headers = {"Authorization": f"Bearer {_login(api_client, 'filter-user')}"}

    response = api_client.get("/api/v1/approval-tasks/todo?biz_type=leave_request", headers=headers)
    assert response.status_code == 200
    assert [item["biz_type"] for item in response.json()["data"]["items"]] == ["leave_request"]
    response = api_client.get("/api/v1/approval-tasks/todo?applicant=张三", headers=headers)
    assert response.status_code == 200
    assert [item["biz_id"] for item in response.json()["data"]["items"]] == [6]


def test_duty_operator_only_sees_own_done_tasks(api_client: TestClient, db_session) -> None:
    room = OrgUnit(code="SELF-DONE-ROOM", name="个人已办机房", type="room")
    db_session.add(room)
    db_session.flush()
    own_person = Person(code="SELF-DONE-OWN", name="本人", person_type="duty_operator", org_unit_id=room.id)
    other_person = Person(code="SELF-DONE-OTHER", name="他人", person_type="duty_operator", org_unit_id=room.id)
    db_session.add_all([own_person, other_person])
    db_session.flush()
    own_user = create_user(db_session, "self-done", "password123", "本人", own_person.id)
    other_user = create_user(db_session, "other-done", "password123", "他人", other_person.id)
    permission = SysPermission(code="approval:record:view_done", name="查看已办", type="api")
    duty_operator = SysRole(code="duty_operator", name="值机员")
    duty_operator.permissions.append(permission)
    db_session.add_all([permission, duty_operator])
    own_user.roles.append(duty_operator)
    other_user.roles.append(duty_operator)
    own_task = create_task(db_session, biz_type="cover_assignment", biz_id=8, node_code="cover_confirm", assignee_user_id=own_user.id, org_unit_id=room.id, snapshot={})
    other_task = create_task(db_session, biz_type="cover_assignment", biz_id=9, node_code="cover_confirm", assignee_user_id=other_user.id, org_unit_id=room.id, snapshot={})
    complete_task(db_session, own_task.id, own_user.id, action="approve", opinion=None, snapshot={})
    complete_task(db_session, other_task.id, other_user.id, action="approve", opinion=None, snapshot={})
    db_session.commit()

    response = api_client.get("/api/v1/approval-tasks/done", headers={"Authorization": f"Bearer {_login(api_client, 'self-done')}"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]["items"]] == [own_task.id]
