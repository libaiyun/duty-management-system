from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_authenticated_user, get_db, resolve_current_room_id
from app.models.approval import ApprovalTask
from app.models.person import Person
from app.models.schedule import (
    CoverAssignment,
    LeaveRequest,
    MonthlySchedule,
    ScheduleDay,
    ScheduleShift,
    ScheduleShiftPerson,
    ShiftSwap,
)
from app.models.shift import ShiftDef
from app.models.user import SysUser
from app.schemas.dashboard import (
    DashboardReminder,
    DashboardResponse,
    DutySummary,
    ManagementDashboard,
    NextDutySummary,
    PersonalDashboard,
)
from app.schemas.response import ApiResponse, ok
from app.services.auth import check_user_permission

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _duty_rows(db: Session, person_id: int, duty_date: date | None = None, after_today: bool = False):
    filters = [ScheduleShiftPerson.person_id == person_id, MonthlySchedule.status == "published"]
    if duty_date is not None:
        filters.append(ScheduleDay.duty_date == duty_date)
    if after_today:
        filters.append(ScheduleDay.duty_date > date.today())
    return db.execute(
        select(ScheduleDay.duty_date, ShiftDef.name, ScheduleShift.start_at, Person.name.label("person_name"))
        .select_from(ScheduleShiftPerson)
        .join(ScheduleShift, ScheduleShift.id == ScheduleShiftPerson.schedule_shift_id)
        .join(ScheduleDay, ScheduleDay.id == ScheduleShift.schedule_day_id)
        .join(MonthlySchedule, MonthlySchedule.id == ScheduleDay.schedule_id)
        .join(ShiftDef, ShiftDef.id == ScheduleShift.shift_def_id)
        .join(Person, Person.id == ScheduleShiftPerson.person_id)
        .where(*filters)
        .order_by(ScheduleDay.duty_date, ScheduleShift.start_at)
    ).all()


@router.get("", response_model=ApiResponse[DashboardResponse])
def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_authenticated_user),
) -> ApiResponse[DashboardResponse]:
    """Return dashboard summaries scoped by business relationship and current room."""
    room_id = resolve_current_room_id(request, db, user)
    today_duties: list[DutySummary] = []
    next_duty: NextDutySummary | None = None
    pending_swap_confirm_count = 0
    pending_cover_confirm_count = 0
    if user.person_id is not None:
        today_duties = [
            DutySummary(duty_date=row.duty_date.isoformat(), shift_name=row.name, persons=[row.person_name])
            for row in _duty_rows(db, user.person_id, duty_date=date.today())
        ]
        next_row = next(iter(_duty_rows(db, user.person_id, after_today=True)), None)
        if next_row is not None:
            next_duty = NextDutySummary(duty_date=next_row.duty_date.isoformat(), shift_name=next_row.name)
        pending_swap_confirm_count = int(db.scalar(select(func.count()).select_from(ShiftSwap).where(
            ShiftSwap.target_person_id == user.person_id,
            ShiftSwap.status == "wait_target_confirm",
        )) or 0)
        pending_cover_confirm_count = int(db.scalar(select(func.count()).select_from(CoverAssignment).where(
            CoverAssignment.cover_person_id == user.person_id,
            CoverAssignment.status == "wait_cover_confirm",
        )) or 0)

    personal = PersonalDashboard(
        today_duties=today_duties,
        next_duty=next_duty,
        pending_swap_confirm_count=pending_swap_confirm_count,
        pending_cover_confirm_count=pending_cover_confirm_count,
    )
    reminders = _personal_reminders(personal)
    can_approve = check_user_permission(db, user, "approval:task:view_todo")
    can_arrange_cover = check_user_permission(db, user, "cover:assignment:view")
    can_view_schedule = check_user_permission(db, user, "schedule:monthly:view")
    if not any((can_approve, can_arrange_cover, can_view_schedule)):
        return ok(DashboardResponse(personal=personal, reminders=reminders))

    schedule_status = db.scalar(select(MonthlySchedule.status).where(MonthlySchedule.org_unit_id == room_id).order_by(MonthlySchedule.updated_at.desc()))
    system_status = []
    if schedule_status is None:
        system_status.append("当前机房尚未生成排班")
    elif schedule_status != "published":
        system_status.append("当前机房存在未发布排班")
    pending_approval_count = int(db.scalar(select(func.count()).select_from(ApprovalTask).where(
        ApprovalTask.org_unit_id == room_id,
        ApprovalTask.status == "pending",
        ApprovalTask.node_code == "director_approval",
    )) or 0) if can_approve else None
    pending_cover_arrangement_count = int(db.scalar(select(func.count()).select_from(CoverAssignment)
        .join(CoverAssignment.leave_request)
        .join(LeaveRequest.schedule_shift)
        .join(ScheduleShift.schedule_day)
        .where(ScheduleDay.schedule.has(org_unit_id=room_id), CoverAssignment.status.in_(("pending_arrangement", "rearrange")))
    ) or 0) if can_arrange_cover else None
    management = ManagementDashboard(
        pending_approval_count=pending_approval_count,
        pending_cover_arrangement_count=pending_cover_arrangement_count,
        schedule_status=schedule_status if can_view_schedule else None,
        system_status=system_status,
    )
    reminders.extend(_management_reminders(management))
    return ok(DashboardResponse(
        personal=personal,
        management=management,
        reminders=reminders,
    ))


def _personal_reminders(personal: PersonalDashboard) -> list[DashboardReminder]:
    reminders: list[DashboardReminder] = []
    if personal.pending_swap_confirm_count:
        reminders.append(DashboardReminder(type="swap_confirm", title="待确认换班", count=personal.pending_swap_confirm_count, path="/swap-request"))
    if personal.pending_cover_confirm_count:
        reminders.append(DashboardReminder(type="cover_confirm", title="待确认顶班", count=personal.pending_cover_confirm_count, path="/my-cover"))
    return reminders


def _management_reminders(management: ManagementDashboard) -> list[DashboardReminder]:
    reminders: list[DashboardReminder] = []
    if management.pending_approval_count:
        reminders.append(DashboardReminder(type="approval", title="待审批", count=management.pending_approval_count, path="/approval"))
    if management.pending_cover_arrangement_count:
        reminders.append(DashboardReminder(type="cover_arrangement", title="待安排顶班", count=management.pending_cover_arrangement_count, path="/leave-records"))
    return reminders
