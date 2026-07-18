from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from app.core.exceptions import BusinessRuleError, ForbiddenError
from app.models.approval import ApprovalTask
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import ActualDuty, MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleVersion
from app.models.user import SysRole
from app.services.auth import create_user
from app.services.shift_swap import create_swap, director_decide, target_confirm, withdraw_or_cancel
from sqlalchemy import select

pytestmark = pytest.mark.usefixtures("create_tables")


def _fixture(db_session):
    room = OrgUnit(code="SWAP-ROOM", name="换班机房", type="room")
    db_session.add(room); db_session.flush()
    people = [Person(code=f"SWAP-P{i}", name=f"人员{i}", person_type="duty_operator", org_unit_id=room.id, participate_schedule=True) for i in range(1, 4)]
    db_session.add_all(people); db_session.flush()
    applicant, target, director_person = people
    applicant_user = create_user(db_session, "swap-applicant", "password123", "申请人", applicant.id)
    target_user = create_user(db_session, "swap-target", "password123", "目标人", target.id)
    director_user = create_user(db_session, "swap-director", "password123", "主任", director_person.id)
    director_role = SysRole(code="room_director", name="机房主任")
    director_user.roles.append(director_role)
    definition = ShiftDef(org_unit_id=room.id, code="swap-shift", name="早班", start_time="00:00", end_time="08:00")
    rule = ShiftRule(org_unit_id=room.id, code="swap-rule", name="换班规则", cycle_days=2, start_date="2026-07-01", persons_per_cell=1)
    db_session.add_all([definition, rule]); db_session.flush()
    version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=2, start_date="2026-07-01", persons_per_cell=1, snapshot={})
    db_session.add(version); db_session.flush()
    schedule = MonthlySchedule(org_unit_id=room.id, rule_id=rule.id, rule_version_id=version.id, status="published")
    db_session.add(schedule); db_session.flush()
    shifts = []
    for number, person in enumerate((applicant, target), start=1):
        day = ScheduleDay(schedule_id=schedule.id, duty_date=date(2026, 7, number), weekday=number, is_legal_holiday=False)
        db_session.add(day); db_session.flush()
        shift = ScheduleShift(schedule_day_id=day.id, shift_def_id=definition.id, start_at=datetime(2026, 7, number, tzinfo=UTC), end_at=datetime(2026, 7, number, 8, tzinfo=UTC))
        db_session.add(shift); db_session.flush()
        db_session.add(ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=person.id, position_no=1))
        db_session.add(ActualDuty(org_unit_id=room.id, schedule_shift_id=shift.id, original_person_id=person.id, actual_person_id=person.id, duty_date=day.duty_date, shift_def_id=definition.id))
        shifts.append(shift)
    db_session.commit()
    return room, applicant_user, target_user, director_user, shifts


def test_mutual_swap_updates_actual_duties_after_confirm_and_director_approval(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="mutual", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=shifts[1].id, reason="调班"), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=True, opinion="同意", room_id=room.id)
    director_decide(db_session, swap.id, director, approve=True, opinion="同意")
    db_session.commit()

    assert swap.status == "effective"
    actuals = db_session.scalars(select(ActualDuty).order_by(ActualDuty.duty_date)).all()
    assert [row.actual_person_id for row in actuals] == [target.person_id, applicant.person_id]
    assert db_session.scalar(select(ApprovalTask).where(ApprovalTask.biz_id == swap.id, ApprovalTask.node_code == "director_approval")).status == "pending"


def test_duplicate_open_swap_is_rejected(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    payload = SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None)
    create_swap(db_session, payload, applicant, room.id)
    with pytest.raises(BusinessRuleError, match="已有未完成"):
        create_swap(db_session, payload, applicant, room.id)


def test_only_target_person_can_confirm_swap(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    with pytest.raises(ForbiddenError, match="目标人员"):
        target_confirm(db_session, swap.id, director, approve=True, opinion=None, room_id=room.id)


def test_target_rejection_keeps_actual_duty_unchanged(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=False, opinion="无法替班", room_id=room.id)

    assert swap.status == "rejected"
    assert db_session.scalar(select(ActualDuty.actual_person_id).where(ActualDuty.schedule_shift_id == shifts[0].id)) == applicant.person_id


def test_director_rejection_keeps_actual_duty_unchanged(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=True, opinion=None, room_id=room.id)
    director_decide(db_session, swap.id, director, approve=False, opinion="排班冲突")

    assert swap.status == "rejected"
    assert db_session.scalar(select(ActualDuty.actual_person_id).where(ActualDuty.schedule_shift_id == shifts[0].id)) == applicant.person_id


def test_applicant_can_withdraw_before_director_approval(db_session) -> None:
    room, applicant, target, _, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    withdraw_or_cancel(db_session, swap.id, applicant)

    assert swap.status == "withdrawn"
    assert db_session.scalar(select(ActualDuty.actual_person_id).where(ActualDuty.schedule_shift_id == shifts[0].id)) == applicant.person_id


def test_applicant_can_cancel_effective_swap_and_restore_actual_duty(db_session) -> None:
    room, applicant, target, director, shifts = _fixture(db_session)
    swap = create_swap(db_session, SimpleNamespace(swap_type="single_cover", source_shift_id=shifts[0].id, target_person_id=target.person_id, target_shift_id=None, reason=None), applicant, room.id)
    target_confirm(db_session, swap.id, target, approve=True, opinion=None, room_id=room.id)
    director_decide(db_session, swap.id, director, approve=True, opinion=None)
    withdraw_or_cancel(db_session, swap.id, applicant, cancel=True)

    assert swap.status == "cancelled"
    assert db_session.scalar(select(ActualDuty.actual_person_id).where(ActualDuty.schedule_shift_id == shifts[0].id)) == applicant.person_id
