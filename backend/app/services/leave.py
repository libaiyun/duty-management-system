from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError, StateConflictError
from app.models.holiday import HolidayCalendar
from app.models.person import Person
from app.models.schedule import CoverAssignment, LeaveRequest, ScheduleDay, ScheduleShift, ScheduleShiftPerson
from app.models.user import SysUser
from app.services.approval import create_task
from app.services.schedule import update_schedule_shift_persons
from app.services.shift_swap import _find_approval_assignee

OPEN_LEAVE_STATUSES = ("wait_director_approval", "approved", "pending_arrangement", "wait_cover_confirm")
COVER_PERSON_TYPES = {"maintenance", "room_director", "deputy_director"}


def _shift(db: Session, shift_id: int, *, for_update: bool = False) -> ScheduleShift:
    statement = select(ScheduleShift).where(ScheduleShift.id == shift_id).options(
        selectinload(ScheduleShift.schedule_day).selectinload(ScheduleDay.schedule),
        selectinload(ScheduleShift.persons),
    )
    if for_update:
        statement = statement.with_for_update()
    shift = db.scalar(statement)
    if shift is None:
        raise NotFoundError(message="排班班次不存在")
    return shift


def _leave(db: Session, leave_id: int) -> LeaveRequest:
    leave = db.scalar(select(LeaveRequest).where(LeaveRequest.id == leave_id).options(
        selectinload(LeaveRequest.applicant),
        selectinload(LeaveRequest.schedule_shift).selectinload(ScheduleShift.schedule_day),
    ))
    if leave is None:
        raise NotFoundError(message="请假申请不存在")
    return leave


def _snapshot(leave: LeaveRequest) -> dict[str, str | int | None]:
    return {"applicant_name": leave.applicant.name, "duty_date": str(leave.schedule_shift.schedule_day.duty_date), "biz_no": leave.biz_no, "summary": "请假审批"}


def create_leave(db: Session, payload: object, user: SysUser, room_id: int) -> LeaveRequest:
    if user.person_id is None:
        raise ForbiddenError(message="当前账号未绑定人员")
    applicant = db.get(Person, user.person_id)
    if applicant is None or applicant.org_unit_id != room_id or applicant.status != "enabled" or applicant.person_type != "duty_operator" or not applicant.participate_schedule:
        raise ForbiddenError(message="只有当前机房启用且参与排班的值机员可以发起请假")
    # Serialise requests for one published shift so a parallel request cannot
    # pass the duplicate check before the first request commits.
    shift = _shift(db, payload.schedule_shift_id, for_update=True)
    if shift.schedule_day.schedule.org_unit_id != room_id or shift.schedule_day.schedule.status != "published":
        raise BusinessRuleError(message="仅能对当前机房已发布班次请假")
    if shift.schedule_day.duty_date < datetime.now().date():
        raise BusinessRuleError(message="历史班次不能发起普通请假")
    if db.scalar(select(HolidayCalendar.id).where(HolidayCalendar.holiday_date == shift.schedule_day.duty_date, HolidayCalendar.is_legal.is_(True), HolidayCalendar.status == "enabled")) is not None:
        raise BusinessRuleError(message="法定节假日班次不允许请假")
    if not any(item.person_id == applicant.id for item in shift.persons):
        raise ForbiddenError(message="仅能对本人排班发起请假")
    if db.scalar(select(LeaveRequest.id).where(LeaveRequest.schedule_shift_id == shift.id, LeaveRequest.applicant_person_id == applicant.id, LeaveRequest.status.in_(OPEN_LEAVE_STATUSES))) is not None:
        raise BusinessRuleError(message="当前班次已有未完成的请假申请")
    director = _find_approval_assignee(db, room_id)
    if director is None:
        raise BusinessRuleError(message="当前机房未配置请假审批账号")
    leave = LeaveRequest(biz_no=f"LV{datetime.now().strftime('%Y%m%d%H%M%S%f')}", applicant_person_id=applicant.id, schedule_shift_id=shift.id, leave_type=payload.leave_type, reason=payload.reason, status="wait_director_approval", submitted_at=datetime.now().astimezone(), created_by=user.id)
    db.add(leave)
    db.flush()
    leave.applicant, leave.schedule_shift = applicant, shift
    create_task(db, biz_type="leave_request", biz_id=leave.id, node_code="director_approval", assignee_user_id=director.id, org_unit_id=room_id, snapshot=_snapshot(leave), created_by=user.id)
    return leave


def withdraw_leave(db: Session, leave_id: int, user: SysUser, room_id: int) -> LeaveRequest:
    leave = _leave(db, leave_id)
    if leave.applicant_person_id != user.person_id:
        raise ForbiddenError(message="仅申请人可撤回请假")
    if leave.schedule_shift.schedule_day.schedule.org_unit_id != room_id:
        raise ForbiddenError(message="仅能操作当前机房请假")
    if leave.status != "wait_director_approval":
        raise StateConflictError(message="当前请假申请不能撤回")
    leave.status, leave.updated_by = "withdrawn", user.id
    return leave


def decide_leave(db: Session, leave_id: int, user: SysUser, *, approve: bool) -> LeaveRequest:
    leave = _leave(db, leave_id)
    if leave.status != "wait_director_approval":
        raise StateConflictError(message="当前请假申请不能审批")
    if approve:
        if leave.schedule_shift.schedule_day.duty_date < datetime.now().date():
            raise BusinessRuleError(message="历史班次不能审批普通请假")
        leave.status, leave.approved_at = "pending_arrangement", datetime.now().astimezone()
        db.add(CoverAssignment(biz_no=f"CV{datetime.now().strftime('%Y%m%d%H%M%S%f')}", leave_request_id=leave.id, status="pending_arrangement", created_by=user.id))
    else:
        leave.status = "rejected"
    leave.updated_by = user.id
    db.flush()
    return leave


def get_cover(db: Session, cover_id: int, *, for_update: bool = False) -> CoverAssignment:
    statement = select(CoverAssignment).where(CoverAssignment.id == cover_id).options(
        selectinload(CoverAssignment.cover_person),
        selectinload(CoverAssignment.leave_request).selectinload(LeaveRequest.applicant),
        selectinload(CoverAssignment.leave_request).selectinload(LeaveRequest.schedule_shift).selectinload(ScheduleShift.schedule_day),
    )
    if for_update:
        statement = statement.with_for_update()
    cover = db.scalar(statement)
    if cover is None:
        raise NotFoundError(message="顶班任务不存在")
    return cover


def arrange_cover(db: Session, cover_id: int, cover_person_id: int, remark: str | None, user: SysUser, room_id: int) -> CoverAssignment:
    cover = get_cover(db, cover_id, for_update=True)
    leave = cover.leave_request
    if leave.schedule_shift.schedule_day.schedule.org_unit_id != room_id:
        raise ForbiddenError(message="仅能管理当前机房顶班")
    if cover.status not in ("pending_arrangement", "rearrange") or leave.status not in ("pending_arrangement", "wait_cover_confirm"):
        raise StateConflictError(message="当前顶班任务不能安排")
    person = db.scalar(select(Person).where(Person.id == cover_person_id).options(selectinload(Person.account)))
    if person is None or person.org_unit_id != room_id or person.status != "enabled" or person.person_type not in COVER_PERSON_TYPES or person.account is None or person.account.status != "enabled":
        raise BusinessRuleError(message="顶班人必须是同机房检修班、机房主任或副主任，且绑定启用账号")
    if person.id == leave.applicant_person_id:
        raise BusinessRuleError(message="值机员不得作为顶班人")
    cover.cover_person_id, cover.remark, cover.status = person.id, remark, "wait_cover_confirm"
    cover.assigned_at, cover.updated_by = datetime.now().astimezone(), user.id
    leave.status, leave.updated_by = "wait_cover_confirm", user.id
    return cover


def confirm_cover(db: Session, cover_id: int, user: SysUser, *, approve: bool, opinion: str | None, room_id: int) -> CoverAssignment:
    cover = get_cover(db, cover_id, for_update=True)
    leave, shift = cover.leave_request, cover.leave_request.schedule_shift
    if shift.schedule_day.schedule.org_unit_id != room_id:
        raise ForbiddenError(message="仅能操作当前机房顶班")
    if cover.cover_person_id != user.person_id:
        raise ForbiddenError(message="仅被安排顶班人可确认")
    if cover.status != "wait_cover_confirm":
        raise StateConflictError(message="当前顶班任务不能确认")
    if shift.schedule_day.duty_date < datetime.now().date():
        raise BusinessRuleError(message="历史班次不能确认顶班")
    if not approve and not (opinion or "").strip():
        raise BusinessRuleError(message="拒绝时必须填写意见")
    if not approve:
        cover.status, cover.remark, cover.updated_by = "rearrange", opinion, user.id
        leave.status, leave.updated_by = "pending_arrangement", user.id
        return cover
    people = list(db.scalars(
        select(ScheduleShiftPerson.person_id)
        .where(ScheduleShiftPerson.schedule_shift_id == shift.id)
        .order_by(ScheduleShiftPerson.position_no)
    ).all())
    if leave.applicant_person_id not in people:
        raise BusinessRuleError(message="请假人不在当前最终排班中")
    update_schedule_shift_persons(db, shift.schedule_day.schedule, shift, [cover.cover_person_id if item == leave.applicant_person_id else item for item in people], cover.remark, change_type="leave_cover", source_biz_no=cover.biz_no, actor_id=user.id, allowed_person_types={"duty_operator", *COVER_PERSON_TYPES})
    cover.status, cover.confirmed_at, cover.updated_by = "effective", datetime.now().astimezone(), user.id
    leave.status, leave.updated_by = "completed", user.id
    return cover


def cancel_cover(db: Session, cover_id: int, reason: str, user: SysUser, room_id: int) -> CoverAssignment:
    """Void an effective cover before its duty date and restore the duty operator."""
    cover = get_cover(db, cover_id, for_update=True)
    leave, shift = cover.leave_request, cover.leave_request.schedule_shift
    if shift.schedule_day.schedule.org_unit_id != room_id:
        raise ForbiddenError(message="仅能管理当前机房顶班")
    if cover.status != "effective":
        raise StateConflictError(message="仅已生效顶班可以作废")
    if shift.schedule_day.duty_date < datetime.now().date():
        raise BusinessRuleError(message="历史班次不能作废顶班")
    people = list(db.scalars(
        select(ScheduleShiftPerson.person_id)
        .where(ScheduleShiftPerson.schedule_shift_id == shift.id)
        .order_by(ScheduleShiftPerson.position_no)
    ).all())
    if cover.cover_person_id not in people:
        raise BusinessRuleError(message="顶班人不在当前最终排班中")
    update_schedule_shift_persons(
        db, shift.schedule_day.schedule, shift,
        [leave.applicant_person_id if item == cover.cover_person_id else item for item in people],
        reason, change_type="leave_cover_cancel", source_biz_no=cover.biz_no, actor_id=user.id,
    )
    cover.status, cover.remark, cover.updated_by = "cancelled", reason, user.id
    return cover
