from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import MonthlySchedule, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.shift import ShiftDef, ShiftRule

pytestmark = pytest.mark.usefixtures("create_tables")


def _create_org(db_session) -> OrgUnit:
    org = OrgUnit(code="test-station", name="测试台站", type="station")
    db_session.add(org)
    db_session.commit()
    return org


def _create_person(db_session, org: OrgUnit, code: str = "P001", name: str = "值班员") -> Person:
    person = Person(code=code, name=name, person_type="duty_operator", org_unit=org)
    db_session.add(person)
    db_session.commit()
    return person


def _create_shift_def(db_session) -> ShiftDef:
    sd = ShiftDef(code="early", name="早班", start_time="00:00", end_time="08:00")
    db_session.add(sd)
    db_session.commit()
    return sd


def _create_rule(db_session) -> ShiftRule:
    rule = ShiftRule(code="rule-broadcast", name="广播规则", station_type="station_broadcast")
    db_session.add(rule)
    db_session.commit()
    return rule


class TestMonthlySchedule:
    """M3-P1-T1: monthly_schedule 模型测试"""

    def test_create_with_defaults(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(
            org_unit_id=org.id,
            year_month="2026-07",
            rule_id=rule.id,
        )
        db_session.add(ms)
        db_session.commit()

        assert ms.id is not None
        assert ms.status == "not_generated"
        assert ms.generated_at is None
        assert ms.published_at is None
        assert ms.locked_at is None
        assert ms.remark is None
        assert ms.version == 1
        assert ms.created_at is not None
        assert ms.updated_at is not None

    def test_org_unit_fk(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-08", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()

        assert ms.org_unit.id == org.id
        assert ms.org_unit.name == "测试台站"

    def test_rule_fk(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-09", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()

        assert ms.rule.id == rule.id

    def test_invalid_org_unit_raises(self, db_session) -> None:
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=99999, year_month="2026-10", rule_id=rule.id)
        db_session.add(ms)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_invalid_rule_raises(self, db_session) -> None:
        org = _create_org(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-11", rule_id=99999)
        db_session.add(ms)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_unique_org_month_active(self, db_session) -> None:
        """同一机房同月份不能有两份活跃排班"""
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms1 = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms1)
        db_session.commit()

        ms2 = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_unique_org_month_soft_deleted(self, db_session) -> None:
        """软删除后可以创建同一机房同月的新排班"""
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms1 = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms1)
        db_session.commit()
        # 软删除
        ms1.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        ms2 = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms2)
        db_session.commit()
        assert ms2.id != ms1.id

    def test_status_readable_strings(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(
            org_unit_id=org.id, year_month="2026-12", rule_id=rule.id,
            status="draft",
        )
        db_session.add(ms)
        db_session.commit()

        assert ms.status == "draft"

    def test_generated_published_locked_timestamps(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        now = datetime.now(timezone.utc)
        ms = MonthlySchedule(
            org_unit_id=org.id, year_month="2026-12", rule_id=rule.id,
            status="locked",
            generated_at=now,
            published_at=now,
            locked_at=now,
        )
        db_session.add(ms)
        db_session.commit()

        assert ms.generated_at == now
        assert ms.published_at == now
        assert ms.locked_at == now


class TestScheduleDay:
    """M3-P1-T1: schedule_day 模型测试"""

    def test_create_with_defaults(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()

        day = ScheduleDay(
            schedule_id=ms.id,
            duty_date=date(2026, 7, 1),
            weekday=2,  # Wednesday
        )
        db_session.add(day)
        db_session.commit()

        assert day.id is not None
        assert day.is_legal_holiday is False
        assert day.holiday_name is None

    def test_with_holiday(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-10", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()

        day = ScheduleDay(
            schedule_id=ms.id,
            duty_date=date(2026, 10, 1),
            weekday=3,
            is_legal_holiday=True,
            holiday_name="国庆节",
        )
        db_session.add(day)
        db_session.commit()

        assert day.is_legal_holiday is True
        assert day.holiday_name == "国庆节"

    def test_cascade_delete_from_schedule(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()

        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()
        day_id = day.id

        db_session.delete(ms)
        db_session.commit()

        assert db_session.get(ScheduleDay, day_id) is None

    def test_schedule_relationship(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()

        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()

        assert day.schedule.id == ms.id


class TestScheduleShift:
    """M3-P1-T1: schedule_shift 模型测试"""

    def test_create_with_defaults(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()

        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id,
            shift_def_id=shift_def.id,
            start_at=start,
            end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        assert shift.id is not None
        assert shift.status == "normal"

    def test_relationships(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()

        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        assert shift.schedule_day.id == day.id
        assert shift.shift_def.code == "early"

    def test_cascade_delete_from_day(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()

        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()
        shift_id = shift.id

        db_session.delete(day)
        db_session.commit()

        assert db_session.get(ScheduleShift, shift_id) is None


class TestScheduleShiftPerson:
    """M3-P1-T1: schedule_shift_person 模型测试"""

    def test_create_with_defaults(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()
        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        person = _create_person(db_session, org)
        sp = ScheduleShiftPerson(
            schedule_shift_id=shift.id,
            person_id=person.id,
        )
        db_session.add(sp)
        db_session.commit()

        assert sp.id is not None
        assert sp.position_no == 1
        assert sp.source_type == "auto"
        assert sp.remark is None

    def test_manual_source_type(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()
        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        person = _create_person(db_session, org)
        sp = ScheduleShiftPerson(
            schedule_shift_id=shift.id,
            person_id=person.id,
            position_no=2,
            source_type="manual",
            remark="手动调整",
        )
        db_session.add(sp)
        db_session.commit()

        assert sp.position_no == 2
        assert sp.source_type == "manual"
        assert sp.remark == "手动调整"

    def test_relationships(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()
        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        person = _create_person(db_session, org)
        sp = ScheduleShiftPerson(
            schedule_shift_id=shift.id, person_id=person.id,
        )
        db_session.add(sp)
        db_session.commit()

        assert sp.schedule_shift.id == shift.id
        assert sp.person.id == person.id

    def test_cascade_delete_from_shift(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()
        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        person = _create_person(db_session, org)
        sp = ScheduleShiftPerson(
            schedule_shift_id=shift.id, person_id=person.id,
        )
        db_session.add(sp)
        db_session.commit()
        sp_id = sp.id

        db_session.delete(shift)
        db_session.commit()

        assert db_session.get(ScheduleShiftPerson, sp_id) is None

    def test_multiple_persons_per_shift(self, db_session) -> None:
        """每班双岗值——同一班次可分配多名人员"""
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        day = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        db_session.add(day)
        db_session.commit()
        shift_def = _create_shift_def(db_session)
        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        p1 = _create_person(db_session, org, "P001", "张三")
        p2 = _create_person(db_session, org, "P002", "李四")
        sp1 = ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=p1.id, position_no=1)
        sp2 = ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=p2.id, position_no=2)
        db_session.add_all([sp1, sp2])
        db_session.commit()

        assert len(shift.persons) == 2
        assert shift.persons[0].person_id == p1.id
        assert shift.persons[1].person_id == p2.id


class TestScheduleCascadeChain:
    """M3-P1-T1: 整条排班链的级联删除验证"""

    def test_delete_monthly_schedule_cascades_all(self, db_session) -> None:
        org = _create_org(db_session)
        rule = _create_rule(db_session)
        ms = MonthlySchedule(org_unit_id=org.id, year_month="2026-07", rule_id=rule.id)
        db_session.add(ms)
        db_session.commit()
        ms_id = ms.id

        shift_def = _create_shift_def(db_session)
        person = _create_person(db_session, org)

        day1 = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 1), weekday=2)
        day2 = ScheduleDay(schedule_id=ms.id, duty_date=date(2026, 7, 2), weekday=3)
        db_session.add_all([day1, day2])
        db_session.commit()

        start = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
        shift = ScheduleShift(
            schedule_day_id=day1.id, shift_def_id=shift_def.id,
            start_at=start, end_at=end,
        )
        db_session.add(shift)
        db_session.commit()

        sp = ScheduleShiftPerson(schedule_shift_id=shift.id, person_id=person.id)
        db_session.add(sp)
        db_session.commit()

        day1_id = day1.id
        day2_id = day2.id
        shift_id = shift.id
        sp_id = sp.id

        db_session.delete(ms)
        db_session.commit()

        assert db_session.get(MonthlySchedule, ms_id) is None
        assert db_session.get(ScheduleDay, day1_id) is None
        assert db_session.get(ScheduleDay, day2_id) is None
        assert db_session.get(ScheduleShift, shift_id) is None
        assert db_session.get(ScheduleShiftPerson, sp_id) is None
        # 人员和班次定义不受影响
        assert db_session.get(Person, person.id) is not None
        assert db_session.get(ShiftDef, shift_def.id) is not None
