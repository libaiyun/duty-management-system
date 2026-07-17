"""M3-P1 integration tests: exceptions, boundaries, permissions, edge cases"""

from datetime import date as _date
from datetime import timedelta

import pytest
from app.core.exceptions import BusinessRuleError
from app.models.organization import OrgUnit
from app.models.person import Person
from app.models.schedule import (
    MonthlySchedule,
    ScheduleDay,
    ScheduleShift,
    ScheduleShiftPerson,
)
from app.models.shift import ShiftDef, ShiftRule, ShiftRuleItem, ShiftRuleVersion
from app.services.schedule import generate_schedule_from_rule, list_schedules

pytestmark = pytest.mark.usefixtures("create_tables")


class TestEdgeCases:
    """M3-P1 boundary and edge case tests"""

    def _setup(self, db_session):
        org = OrgUnit(code="ec_org", name="边界测试", type="room")
        p1 = Person(code="EC01", name="A", person_type="duty_operator", org_unit=org, participate_schedule=True)
        p2 = Person(code="EC02", name="B", person_type="duty_operator", org_unit=org, participate_schedule=True)
        sd = ShiftDef(org_unit=org, code="ec_shift", name="班次", start_time="00:00", end_time="08:00", display_order=1)
        db_session.add_all([org, p1, p2, sd])
        db_session.commit()
        return org, [p1, p2], sd

    def test_generate_with_empty_items(self, db_session) -> None:
        """M3-P1: 持久化版本无 items 时返回人类可读的业务错误"""
        org, persons, sd = self._setup(db_session)
        rule = ShiftRule(
            code="ec_empty", name="空items",
            cycle_days=1, start_date="2027-01-01", persons_per_cell=1,
            org_unit_id=org.id,
        )
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=1,
            start_date="2027-01-01", persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.commit()

        with pytest.raises(BusinessRuleError, match="周期天数"):
            generate_schedule_from_rule(db_session, rule, v, total_days=5)

    def test_generate_with_incomplete_persisted_version_raises_business_error(self, db_session) -> None:
        org, persons, sd = self._setup(db_session)
        rule = ShiftRule(
            code="ec_incomplete", name="不完整版本", cycle_days=2,
            start_date="2027-01-01", persons_per_cell=1, org_unit_id=org.id,
        )
        db_session.add(rule)
        db_session.flush()
        version = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=2,
            start_date="2027-01-01", persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(version)
        db_session.flush()
        db_session.add(ShiftRuleItem(
            version_id=version.id, day_no=1, cell_persons={str(sd.id): [persons[0].id]},
        ))
        db_session.commit()

        with pytest.raises(BusinessRuleError, match="周期天数"):
            generate_schedule_from_rule(db_session, rule, version, total_days=0)

    def test_generate_without_org_unit(self, db_session) -> None:
        """M3-P1: 无 org_unit 时返回 0"""
        rule = ShiftRule(
            code="ec_noorg", name="无机房",
            cycle_days=1, start_date="2027-01-01", persons_per_cell=1,
        )
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=1,
            start_date="2027-01-01", persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.commit()

        result = generate_schedule_from_rule(db_session, rule, v)
        assert result == 0

    def test_cell_persons_with_missing_shift_def_is_rejected(self, db_session) -> None:
        """M3-P1: cell_persons 不得引用不存在的班次。"""
        org, persons, sd = self._setup(db_session)
        rule = ShiftRule(
            code="ec_missing_sd", name="缺失班次",
            cycle_days=1, start_date="2027-01-01", persons_per_cell=1,
            org_unit_id=org.id,
        )
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=1,
            start_date="2027-01-01", persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()
        # reference a non-existent shift_def
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=1, cell_persons={
            "99999": [persons[0].id], str(sd.id): [persons[0].id],
        }))
        db_session.commit()

        with pytest.raises(BusinessRuleError, match="当前机房的启用班次"):
            generate_schedule_from_rule(db_session, rule, v, total_days=0)

    def test_holidays_with_none_matching(self, db_session) -> None:
        """M3-P1: 无匹配节假日时 is_legal_holiday 为 False"""
        org, persons, sd = self._setup(db_session)
        rule = ShiftRule(
            code="ec_noholiday", name="无节假日",
            cycle_days=1, start_date="2027-03-01", persons_per_cell=1,
            org_unit_id=org.id,
        )
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=1,
            start_date="2027-03-01", persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=1, cell_persons={
            str(sd.id): [persons[0].id],
        }))
        db_session.commit()

        generate_schedule_from_rule(db_session, rule, v, total_days=3)
        ms = db_session.query(MonthlySchedule).filter(
            MonthlySchedule.org_unit_id == org.id
        ).first()
        days = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == ms.id
        ).all()
        for d in days:
            assert d.is_legal_holiday is False
            assert d.holiday_name is None

    def test_multiple_cycle_repetitions(self, db_session) -> None:
        """M3-P1: 6天循环 × 60天 = 10次完整循环"""
        org, persons, sd = self._setup(db_session)
        rule = ShiftRule(
            code="ec_60days", name="60天",
            cycle_days=6, start_date="2027-01-01", persons_per_cell=1,
            org_unit_id=org.id,
        )
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=6,
            start_date="2027-01-01", persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()
        for day_no in range(1, 7):
            pid = persons[0].id if day_no % 2 == 1 else persons[1].id
            db_session.add(ShiftRuleItem(version_id=v.id, day_no=day_no, cell_persons={
                str(sd.id): [pid],
            }))
        db_session.commit()

        result = generate_schedule_from_rule(db_session, rule, v, total_days=60)
        assert result == 61  # from Jan 1 to Mar 2 inclusive = 61 days

        ms = db_session.query(MonthlySchedule).filter(
            MonthlySchedule.org_unit_id == org.id
        ).first()
        # Verify day 1 and day 7 have same person (6-day cycle)
        d1 = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == ms.id, ScheduleDay.duty_date == _date(2027, 1, 1)
        ).first()
        d7 = db_session.query(ScheduleDay).filter(
            ScheduleDay.schedule_id == ms.id, ScheduleDay.duty_date == _date(2027, 1, 7)
        ).first()
        s1 = db_session.query(ScheduleShift).filter(ScheduleShift.schedule_day_id == d1.id).first()
        s7 = db_session.query(ScheduleShift).filter(ScheduleShift.schedule_day_id == d7.id).first()
        sp1 = db_session.query(ScheduleShiftPerson).filter(ScheduleShiftPerson.schedule_shift_id == s1.id).first()
        sp7 = db_session.query(ScheduleShiftPerson).filter(ScheduleShiftPerson.schedule_shift_id == s7.id).first()
        assert sp1.person_id == sp7.person_id

    def test_start_date_in_past_generates_anyway(self, db_session) -> None:
        """M3-P1: start_date 在过去时生成功能仍正常工作"""
        org, persons, sd = self._setup(db_session)
        rule = ShiftRule(
            code="ec_past", name="过去日期",
            cycle_days=1, start_date="2025-01-01", persons_per_cell=1,
            org_unit_id=org.id,
        )
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=1,
            start_date="2025-01-01", persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=v.id, day_no=1, cell_persons={
            str(sd.id): [persons[0].id],
        }))
        db_session.commit()

        result = generate_schedule_from_rule(db_session, rule, v, total_days=10)
        assert result > 0

    def test_same_version_generation_extends_coverage_without_recreating_days(self, db_session) -> None:
        """M3-P1: 重复生成同一版本时只追加缺失日期。"""
        org, persons, sd = self._setup(db_session)
        start_date = _date.today() + timedelta(days=1)
        rule = ShiftRule(
            code="ec_extend", name="滚动续期", cycle_days=1,
            start_date=start_date.isoformat(), persons_per_cell=1, org_unit_id=org.id,
        )
        db_session.add(rule)
        db_session.flush()
        version = ShiftRuleVersion(
            rule_id=rule.id, version_no=1, cycle_days=1,
            start_date=start_date.isoformat(), persons_per_cell=1,
            snapshot={"days": []}, status="published",
        )
        db_session.add(version)
        db_session.flush()
        db_session.add(ShiftRuleItem(
            version_id=version.id, day_no=1, cell_persons={str(sd.id): [persons[0].id]},
        ))
        db_session.commit()

        assert generate_schedule_from_rule(db_session, rule, version, total_days=2) == 3
        schedule = db_session.query(MonthlySchedule).filter_by(org_unit_id=org.id).one()
        first_day = db_session.query(ScheduleDay).filter_by(
            schedule_id=schedule.id, duty_date=start_date,
        ).one()

        assert generate_schedule_from_rule(
            db_session, rule, version, through_date=start_date + timedelta(days=375),
        ) == 373
        assert db_session.query(ScheduleDay).filter_by(schedule_id=schedule.id).count() == 376
        assert db_session.query(ScheduleDay).filter_by(
            schedule_id=schedule.id, duty_date=start_date,
        ).one().id == first_day.id

        assert generate_schedule_from_rule(
            db_session, rule, version, through_date=start_date + timedelta(days=375),
        ) == 0

        generated_at = schedule.generated_at
        published_at = schedule.published_at
        assert generate_schedule_from_rule(
            db_session, rule, version, through_date=start_date + timedelta(days=375),
        ) == 0
        assert schedule.generated_at == generated_at
        assert schedule.published_at == published_at


class TestSchedulePermissions:
    """M3-P1 permission and data scope tests"""

    def test_list_schedules_empty_scope(self, db_session) -> None:
        """M3-P1: 空 scope_id 集合返回空"""
        from app.services.schedule import list_schedules
        schedules, total = list_schedules(db_session, org_unit_ids=set())
        assert total == 0
        assert schedules == []

    def test_list_schedules_specific_org(self, db_session) -> None:
        """M3-P1: 指定 org_unit_id 过滤"""
        from app.services.schedule import list_schedules
        org_a = OrgUnit(code="perm_a", name="A", type="room")
        org_b = OrgUnit(code="perm_b", name="B", type="room")
        db_session.add_all([org_a, org_b])
        db_session.commit()

        rule = ShiftRule(code="perm_rule", name="R", cycle_days=1, start_date="2027-01-01", persons_per_cell=1)
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date="2027-01-01", persons_per_cell=1, snapshot={"days": []})
        db_session.add(v)
        db_session.commit()

        ms_a = MonthlySchedule(org_unit_id=org_a.id, rule_id=rule.id, rule_version_id=v.id)
        ms_b = MonthlySchedule(org_unit_id=org_b.id, rule_id=rule.id, rule_version_id=v.id)
        db_session.add_all([ms_a, ms_b])
        db_session.commit()

        schedules, total = list_schedules(db_session, org_unit_id=org_a.id)
        assert total == 1
        assert schedules[0].org_unit_id == org_a.id

        schedules2, total2 = list_schedules(db_session, org_unit_id=99999)
        assert total2 == 0

    def test_list_schedules_with_scoped_ids(self, db_session) -> None:
        """M3-P1: 数据范围过滤"""
        from app.services.schedule import list_schedules
        org_a = OrgUnit(code="scope_a", name="SA", type="room")
        org_b = OrgUnit(code="scope_b", name="SB", type="room")
        org_c = OrgUnit(code="scope_c", name="SC", type="room")
        db_session.add_all([org_a, org_b, org_c])
        db_session.commit()

        rule = ShiftRule(code="scope_rule", name="R", cycle_days=1, start_date="2027-01-01", persons_per_cell=1)
        db_session.add(rule)
        db_session.flush()
        v = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date="2027-01-01", persons_per_cell=1, snapshot={"days": []})
        db_session.add(v)
        db_session.commit()

        for org in [org_a, org_b, org_c]:
            ms = MonthlySchedule(org_unit_id=org.id, rule_id=rule.id, rule_version_id=v.id)
            db_session.add(ms)
        db_session.commit()

        # User can see A and B but not C
        schedules, total = list_schedules(db_session, org_unit_ids={org_a.id, org_b.id})
        assert total == 2
        org_ids = {s.org_unit_id for s in schedules}
        assert org_a.id in org_ids
        assert org_b.id in org_ids
        assert org_c.id not in org_ids

        # User tries to query C outside their scope
        schedules3, total3 = list_schedules(db_session, org_unit_ids={org_a.id}, org_unit_id=org_c.id)
        assert total3 == 0


class TestSchedulePerformance:
    def test_generation_preloads_shift_defs_and_existing_days(self, db_session, monkeypatch) -> None:
        org, persons, sd = TestEdgeCases()._setup(db_session)
        rule = ShiftRule(code="ec_bulk", name="批量生成", cycle_days=1, start_date="2027-01-01", persons_per_cell=1, org_unit_id=org.id)
        db_session.add(rule)
        db_session.flush()
        version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date="2027-01-01", persons_per_cell=1, snapshot={"days": []}, status="published")
        db_session.add(version)
        db_session.flush()
        db_session.add(ShiftRuleItem(version_id=version.id, day_no=1, cell_persons={str(sd.id): [persons[0].id]}))
        db_session.commit()

        statements: list[str] = []
        original_scalars = db_session.scalars

        def track_scalars(statement, *args, **kwargs):
            statements.append(str(statement))
            return original_scalars(statement, *args, **kwargs)

        monkeypatch.setattr(db_session, "scalars", track_scalars)
        generate_schedule_from_rule(db_session, rule, version, total_days=10)

        assert sum("FROM shift_def" in statement for statement in statements) == 1
        assert sum("FROM schedule_day" in statement for statement in statements) == 1

    def test_list_schedules_does_not_eagerly_load_schedule_tree(self, db_session, monkeypatch) -> None:
        org, _persons, _sd = TestEdgeCases()._setup(db_session)
        rule = ShiftRule(code="ec_summary", name="摘要", cycle_days=1, start_date="2027-01-01", persons_per_cell=1)
        db_session.add(rule)
        db_session.flush()
        version = ShiftRuleVersion(rule_id=rule.id, version_no=1, cycle_days=1, start_date="2027-01-01", persons_per_cell=1, snapshot={"days": []})
        db_session.add(version)
        db_session.flush()
        db_session.add(MonthlySchedule(org_unit_id=org.id, rule_id=rule.id, rule_version_id=version.id))
        db_session.commit()

        statements: list[str] = []
        original_scalars = db_session.scalars

        def track_scalars(statement, *args, **kwargs):
            statements.append(str(statement))
            return original_scalars(statement, *args, **kwargs)

        monkeypatch.setattr(db_session, "scalars", track_scalars)
        list_schedules(db_session, org_unit_id=org.id)

        assert not any("FROM schedule_day" in statement for statement in statements)
