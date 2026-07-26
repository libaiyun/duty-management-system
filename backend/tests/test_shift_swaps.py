from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.core.exceptions import BusinessRuleError, ForbiddenError
from app.models.approval import ApprovalTask
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import DutyChangeLedger, MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysPermission, SysRole
from app.services.auth import create_user
from app.services.shift_swap import create_swap, director_decide, target_confirm, withdraw_or_cancel
from sqlalchemy import select

pytestmark = pytest.mark.usefixtures("create_tables")


def _fixture(db_session):
    room = OrgUnit(code="SWAP-ROOM", name="换班机房", type="room")
    db_session.add(room)
    db_session.flush()
    people = [Person(code=f"SWAP-P{i}", name=f"人员{i}", person_type="duty_operator", org_unit_id=room.id, participate_schedule=True) for i in range(1, 4)]
    db_session.add_all(people)
    db_session.flush()
    applicant, target, director_person = people
    applicant_user = create_user(db_session, "swap-applicant", "password123", "申请人", applicant.id)
    target_user = create_user(db_session, "swap-target", "password123", "目标人", target.id)
    director_user = create_user(db_session, "swap-director", "password123", "主任", director_person.id)
    director_role = SysRole(code="room_director", name="机房主任")
    director_role.permissions.append(SysPermission(
        code="approval:task:view_todo", name="处理审批任务", type="api",
    ))
    director_user.roles.append(director_role)
    definition = ShiftDef(org_unit_id=room.id, code="swap-shift", name="早班", start_time="00:00", end_time="08:00")
    start_date = date.today() + timedelta(days=1)
    rule = ShiftRule(org_unit_id=room.id, code="swap-rule", name="换班规则", cycle_days=2, start_date=start_date.isoformat(), persons_per_cell=1)
    db_session.add_all([definition, rule])
    db_session.flush()
    version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=2, start_date=start_date.isoformat(), persons_per_cell=1, snapshot={})
    db_session.add(version)
    db_session.flush()
    schedule = MonthlySchedule(org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id, status="published")
    db_session.add(schedule)
    db_session.flush()
    shifts = []
    for number, person in enumerate((applicant, target)):
        duty_date = start_date + timedelta(days=number)
        day = ScheduleDay(schedule_id=schedule.id, duty_date=duty_date, weekday=duty_date.weekday(), is_legal_holiday=False)
        db_session.add(day)
        db_session.flush()
        shift = ScheduleShift(schedule_day_id=day.id, shift_def_id=definition.id, start_at=datetime.combine(duty_date, datetime.min.time(), UTC), end_at=datetime.combine(duty_date, datetime.min.time(), UTC) + timedelta(hours=8))
        db_session.add(shift)
        db_session.flush()
        db_session.add(ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=person.id, position_no=1))
        shifts.append(shift)
    db_session.commit()
    return room, applicant_user, target_user, director_user, shifts


def test_mutual_swap_updates_final_schedule_after_confirm_and_director_approval(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="mutual", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=shifts[1].id, reason="调班"), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=True, opinion="同意", room_id=room.id)
    director_decide(db_session, swap.id, director, approve=True, opinion="同意")
    db_session.commit()

    assert swap.status == "effective"
    assert db_session.scalars(select(ScheduleShiftPerson.person_id).order_by(ScheduleShiftPerson.schedule_shift_id)).all() == [target.person_id, applicant.person_id]
    assert db_session.scalars(select(DutyChangeLedger).where(DutyChangeLedger.change_type == "swap")).all()
    assert db_session.scalar(select(ApprovalTask).where(ApprovalTask.biz_id == swap.id, ApprovalTask.node_code == "director_approval")).status == "pending"


def test_duplicate_open_swap_is_rejected(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    payload = SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None)
    create_swap(db_session, payload, applicant, room.id)
    with pytest.raises(BusinessRuleError, match="已有未完成"):
        create_swap(db_session, payload, applicant, room.id)


def test_swap_rejects_target_who_is_not_a_participating_duty_operator(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    target_person = db_session.get(Person, target.person_id)
    assert target_person is not None
    target_person.person_type = "maintenance"
    target_person.participate_schedule = False
    with pytest.raises(BusinessRuleError, match="参与排班的值机员"):
        create_swap(
            db_session,
            SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None),
            applicant,
            room.id,
        )


def test_swap_rejects_applicant_who_is_not_a_participating_duty_operator(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    applicant_person = db_session.get(Person, applicant.person_id)
    assert applicant_person is not None
    applicant_person.person_type = "maintenance"
    applicant_person.participate_schedule = False

    with pytest.raises(ForbiddenError, match="参与排班的值机员"):
        create_swap(
            db_session,
            SimpleNamespace(
                swap_type="single_cover", source_shift_id=shifts[0].id,
                target_person_id=target.person_id, target_shift_id=None, reason=None,
            ),
            applicant,
            room.id,
        )


def test_target_confirmation_requires_an_enabled_director_account(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    director.status = "disabled"
    swap = create_swap(
        db_session,
        SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None),
        applicant,
        room.id,
    )

    with pytest.raises(BusinessRuleError, match="未配置审批管理员账号"):
        target_confirm(db_session, swap.id, target, approve=True, opinion="同意", room_id=room.id)


def test_only_target_person_can_confirm_swap(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    with pytest.raises(ForbiddenError, match="目标人员"):
        target_confirm(db_session, swap.id, director, approve=True, opinion=None, room_id=room.id)


def test_target_rejection_keeps_final_schedule_unchanged(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=False, opinion="无法替班", room_id=room.id)

    assert swap.status == "rejected"
    assert db_session.scalar(select(ScheduleShiftPerson.person_id).where(ScheduleShiftPerson.schedule_shift_id == shifts[0].id)) == applicant.person_id


def test_director_rejection_keeps_final_schedule_unchanged(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=True, opinion=None, room_id=room.id)
    director_decide(db_session, swap.id, director, approve=False, opinion="排班冲突")

    assert swap.status == "rejected"
    assert db_session.scalar(select(ScheduleShiftPerson.person_id).where(ScheduleShiftPerson.schedule_shift_id == shifts[0].id)) == applicant.person_id


def test_applicant_can_withdraw_before_director_approval(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    withdraw_or_cancel(db_session, swap.id, applicant)

    assert swap.status == "withdrawn"
    assert db_session.scalar(select(ScheduleShiftPerson.person_id).where(ScheduleShiftPerson.schedule_shift_id == shifts[0].id)) == applicant.person_id


def test_withdrawing_swap_cancels_its_pending_confirmation_task(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(
        swap_type="single_cover", source_shift_id=shifts[0].id,
        target_person_id=target.person_id, target_shift_id=None, reason=None,
    ), applicant, room.id)

    withdraw_or_cancel(db_session, swap.id, applicant)

    task = db_session.scalar(select(ApprovalTask).where(
        ApprovalTask.biz_type == "shift_swap", ApprovalTask.biz_id == swap.id,
        ApprovalTask.node_code == "target_confirm",
    ))
    assert task is not None
    assert task.status == "cancelled"


def test_applicant_can_cancel_effective_swap_and_restore_final_schedule(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=True, opinion=None, room_id=room.id)
    director_decide(db_session, swap.id, director, approve=True, opinion=None)
    withdraw_or_cancel(db_session, swap.id, applicant, cancel=True)

    assert swap.status == "cancelled"
    assert db_session.scalar(select(ScheduleShiftPerson.person_id).where(ScheduleShiftPerson.schedule_shift_id == shifts[0].id)) == applicant.person_id


def test_swap_cannot_be_confirmed_after_source_shift_becomes_historical(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(
        swap_type="single_cover", source_shift_id=shifts[0].id,
        target_person_id=target.person_id, target_shift_id=None, reason=None,
    ), applicant, room.id)
    shifts[0].schedule_day.duty_date = date.today() - timedelta(days=1)
    db_session.flush()

    with pytest.raises(BusinessRuleError, match="历史班次"):
        target_confirm(db_session, swap.id, target, approve=True, opinion=None, room_id=room.id)


def test_effective_swap_cannot_be_cancelled_after_shift_becomes_historical(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(
        swap_type="single_cover", source_shift_id=shifts[0].id,
        target_person_id=target.person_id, target_shift_id=None, reason=None,
    ), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=True, opinion=None, room_id=room.id)
    director_decide(db_session, swap.id, director, approve=True, opinion=None)
    shifts[0].schedule_day.duty_date = date.today() - timedelta(days=1)
    db_session.flush()

    with pytest.raises(BusinessRuleError, match="历史班次"):
        withdraw_or_cancel(db_session, swap.id, applicant, cancel=True)
