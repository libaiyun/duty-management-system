from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError, StateConflictError
from app.models.approval import ApprovalTask
from app.models.person import Person
from app.models.schedule import ScheduleDay, ScheduleShift, ShiftSwap
from app.models.user import SysRole, SysUser
from app.services.approval import complete_task, create_task
from app.services.schedule import update_schedule_shift_persons

OPEN_STATUSES = ("draft", "wait_target_confirm", "wait_director_approval")


def _shift(db: Session, shift_id: int) -> ScheduleShift:
    shift = db.scalar(select(ScheduleShift).where(ScheduleShift.id == shift_id).options(
        selectinload(ScheduleShift.schedule_day).selectinload(ScheduleDay.schedule),
        selectinload(ScheduleShift.persons),
    ))
    if shift is None:
        raise NotFoundError(message="排班班次不存在")
    return shift


def _assert_available(db: Session, shift: ScheduleShift, person_id: int) -> None:
    schedule = shift.schedule_day.schedule
    if schedule.status != "published":
        raise BusinessRuleError(message="仅已发布班次可以申请换班")
    if shift.schedule_day.duty_date < datetime.now().date():
        raise BusinessRuleError(message="历史班次不能发起普通换班")
    if any(p.person_id == person_id for p in shift.persons) is False:
        raise ForbiddenError(message="仅能对本人排班发起换班")
    if db.scalar(select(ShiftSwap.id).where(
        ShiftSwap.status.in_(OPEN_STATUSES),
        or_(ShiftSwap.source_shift_id == shift.id, ShiftSwap.target_shift_id == shift.id),
    )) is not None:
        raise BusinessRuleError(message="当前班次已有未完成的换班申请")


def _snapshot(swap: ShiftSwap) -> dict[str, str | int | None]:
    return {
        "applicant_name": swap.applicant.name, "target_name": swap.target_person.name,
        "duty_date": str(swap.source_shift.schedule_day.duty_date),
        "summary": "互换班次" if swap.swap_type == "mutual" else "单向替班",
        "biz_no": swap.biz_no,
    }


def create_swap(db: Session, payload, user: SysUser, room_id: int) -> ShiftSwap:
    if user.person_id is None:
        raise ForbiddenError(message="当前账号未绑定人员")
    source = _shift(db, payload.source_shift_id)
    if source.schedule_day.schedule.org_unit_id != room_id:
        raise ForbiddenError(message="仅能对当前机房的班次发起换班")
    _assert_available(db, source, user.person_id)
    target = db.get(Person, payload.target_person_id)
    if target is None or target.org_unit_id != room_id or target.status != "enabled" or target.id == user.person_id \
            or target.person_type != "duty_operator" or not target.participate_schedule:
        raise BusinessRuleError(message="目标人员必须是同机房启用且参与排班的值机员，且不能为本人")
    target_shift = None
    if payload.swap_type == "mutual":
        target_shift = _shift(db, payload.target_shift_id)
        if target_shift.id == source.id:
            raise BusinessRuleError(message="互换班次不能选择同一班次")
        _assert_available(db, target_shift, target.id)
        if target_shift.schedule_day.schedule_id != source.schedule_day.schedule_id or target_shift.schedule_day.schedule.org_unit_id != room_id:
            raise BusinessRuleError(message="互换班次必须属于同一排班")
    target_user = target.account
    if target_user is None or target_user.status != "enabled":
        raise BusinessRuleError(message="目标人员必须绑定启用账号")
    swap = ShiftSwap(
        biz_no=f"SW{datetime.now().strftime('%Y%m%d%H%M%S%f')}", swap_type=payload.swap_type,
        applicant_person_id=user.person_id, source_shift_id=source.id, target_person_id=target.id,
        target_shift_id=target_shift.id if target_shift else None, reason=payload.reason,
        status="wait_target_confirm", submitted_at=datetime.now().astimezone(), created_by=user.id,
    )
    db.add(swap)
    db.flush()
    swap.applicant = db.get(Person, user.person_id)
    swap.target_person = target
    swap.source_shift = source
    create_task(db, biz_type="shift_swap", biz_id=swap.id, node_code="target_confirm", assignee_user_id=target_user.id, org_unit_id=room_id, snapshot=_snapshot(swap), created_by=user.id)
    db.flush()
    return swap


def target_confirm(db: Session, swap_id: int, user: SysUser, *, approve: bool, opinion: str | None, room_id: int) -> ShiftSwap:
    swap = get_swap(db, swap_id)
    if swap.target_person_id != user.person_id:
        raise ForbiddenError(message="仅目标人员可确认换班")
    if swap.status != "wait_target_confirm":
        raise StateConflictError(message="当前换班单不能确认")
    if not approve and not (opinion or "").strip():
        raise BusinessRuleError(message="拒绝时必须填写意见")
    task = db.scalar(select(ApprovalTask).where(ApprovalTask.biz_type == "shift_swap", ApprovalTask.biz_id == swap.id, ApprovalTask.node_code == "target_confirm", ApprovalTask.status == "pending"))
    if task is None:
        raise StateConflictError(message="确认待办不存在或已处理")
    complete_task(db, task.id, user.id, action="approve" if approve else "reject", opinion=opinion, snapshot=_snapshot(swap))
    if not approve:
        swap.status = "rejected"
        swap.updated_by = user.id
        return swap
    director = db.scalar(
        select(SysUser)
        .join(SysUser.roles)
        .join(Person, SysUser.person_id == Person.id)
        .where(
            Person.org_unit_id == room_id,
            SysUser.status == "enabled",
            SysRole.code.in_(("room_director", "deputy_director")),
        )
        .order_by(SysUser.id)
    )
    if director is None:
        raise BusinessRuleError(message="当前机房未配置主任或副主任账号")
    swap.status = "wait_director_approval"
    swap.updated_by = user.id
    create_task(db, biz_type="shift_swap", biz_id=swap.id, node_code="director_approval", assignee_user_id=director.id, org_unit_id=room_id, snapshot=_snapshot(swap), created_by=user.id)
    return swap


def director_decide(db: Session, swap_id: int, user: SysUser, *, approve: bool, opinion: str | None) -> ShiftSwap:
    swap = get_swap(db, swap_id)
    if swap.status != "wait_director_approval":
        raise StateConflictError(message="当前换班单不能审批")
    if not approve:
        swap.status = "rejected"
        swap.updated_by = user.id
        return swap
    source = _shift(db, swap.source_shift_id)
    source_people = [person.person_id for person in source.persons]
    if swap.applicant_person_id not in source_people:
        raise BusinessRuleError(message="原班次最终排班人员不存在")
    if swap.swap_type == "mutual":
        target = _shift(db, swap.target_shift_id)
        target_people = [person.person_id for person in target.persons]
        if swap.target_person_id not in target_people:
            raise BusinessRuleError(message="目标班次最终排班人员不存在")
        update_schedule_shift_persons(
            db, source.schedule_day.schedule, source,
            [swap.target_person_id if pid == swap.applicant_person_id else pid for pid in source_people],
            swap.reason, change_type="swap", source_biz_no=swap.biz_no, actor_id=user.id,
        )
        update_schedule_shift_persons(
            db, target.schedule_day.schedule, target,
            [swap.applicant_person_id if pid == swap.target_person_id else pid for pid in target_people],
            swap.reason, change_type="swap", source_biz_no=swap.biz_no, actor_id=user.id,
        )
    else:
        update_schedule_shift_persons(
            db, source.schedule_day.schedule, source,
            [swap.target_person_id if pid == swap.applicant_person_id else pid for pid in source_people],
            swap.reason, change_type="swap", source_biz_no=swap.biz_no, actor_id=user.id,
        )
    swap.status = "effective"
    swap.effective_at = datetime.now().astimezone()
    swap.updated_by = user.id
    return swap


def withdraw_or_cancel(db: Session, swap_id: int, user: SysUser, *, cancel: bool = False) -> ShiftSwap:
    swap = get_swap(db, swap_id)
    if swap.applicant_person_id != user.person_id:
        raise ForbiddenError(message="仅申请人可操作换班单")
    allowed = ("approved", "effective") if cancel else OPEN_STATUSES
    if swap.status not in allowed:
        raise StateConflictError(message="当前换班单不能撤回或作废")
    swap.status = "cancelled" if cancel else "withdrawn"
    swap.updated_by = user.id
    if cancel:
        source = _shift(db, swap.source_shift_id)
        update_schedule_shift_persons(
            db, source.schedule_day.schedule, source,
            [swap.applicant_person_id if pid == swap.target_person_id else pid for pid in [p.person_id for p in source.persons]],
            "换班作废", change_type="swap_cancel", source_biz_no=swap.biz_no, actor_id=user.id,
        )
        if swap.target_shift_id:
            target = _shift(db, swap.target_shift_id)
            update_schedule_shift_persons(
                db, target.schedule_day.schedule, target,
                [swap.target_person_id if pid == swap.applicant_person_id else pid for pid in [p.person_id for p in target.persons]],
                "换班作废", change_type="swap_cancel", source_biz_no=swap.biz_no, actor_id=user.id,
            )
    return swap


def get_swap(db: Session, swap_id: int) -> ShiftSwap:
    swap = db.scalar(select(ShiftSwap).where(ShiftSwap.id == swap_id).options(selectinload(ShiftSwap.applicant), selectinload(ShiftSwap.target_person), selectinload(ShiftSwap.source_shift).selectinload(ScheduleShift.schedule_day), selectinload(ShiftSwap.target_shift).selectinload(ScheduleShift.schedule_day)))
    if swap is None:
        raise NotFoundError(message="换班单不存在")
    return swap
