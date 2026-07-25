from datetime import UTC, date, datetime, time

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import RequirePermission, get_authenticated_user, get_db, get_page_params, resolve_current_room_id
from app.core.exceptions import NotFoundError
from app.models.approval import ApprovalRecord, ApprovalTask
from app.models.schedule import ShiftSwap
from app.models.user import SysUser
from app.schemas.approval import ApprovalActionRequest, ApprovalRecordResponse, ApprovalTaskResponse
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.services.approval import complete_task
from app.services.auth import check_user_permission
from app.services.shift_swap import director_decide

router = APIRouter(prefix="/approval-tasks", tags=["approval-tasks"])
records_router = APIRouter(prefix="/approval-records", tags=["approval-records"])


def _response(task: ApprovalTask, opinion: str | None = None) -> ApprovalTaskResponse:
    snapshot = task.records[-1].snapshot_json if task.records else {}
    return ApprovalTaskResponse(id=task.id, biz_type=task.biz_type, biz_id=task.biz_id, node_code=task.node_code, status=task.status, arrived_at=task.arrived_at, handled_at=task.handled_at, snapshot=snapshot, opinion=opinion)


def _visibility_filter(user: SysUser, room_id: int) -> ColumnElement[bool]:
    return and_(
        ApprovalTask.org_unit_id == room_id,
        or_(
            ApprovalTask.node_code == "director_approval",
            ApprovalTask.assignee_user_id == user.id,
        ),
    )


def _list(
    db: Session, user: SysUser, room_id: int, statuses: tuple[str, ...], paging: PageParams,
    biz_type: str | None, applicant: str | None, result: str | None, personal_done: bool,
    arrived_from: date | None, arrived_to: date | None,
) -> PageResponse[ApprovalTaskResponse]:
    filters = [_visibility_filter(user, room_id), ApprovalTask.status.in_(statuses)]
    if personal_done:
        filters.append(ApprovalTask.assignee_user_id == user.id)
    if biz_type:
        filters.append(ApprovalTask.biz_type == biz_type)
    if applicant:
        filters.append(exists(select(ApprovalRecord.id).where(
            ApprovalRecord.task_id == ApprovalTask.id,
            ApprovalRecord.snapshot_json["applicant_name"].as_string().contains(applicant),
        )))
    if result:
        filters.append(ApprovalTask.status == result)
    if arrived_from:
        filters.append(ApprovalTask.arrived_at >= datetime.combine(arrived_from, time.min, UTC))
    if arrived_to:
        filters.append(ApprovalTask.arrived_at <= datetime.combine(arrived_to, time.max, UTC))
    stmt = select(ApprovalTask).options(selectinload(ApprovalTask.records)).where(*filters).order_by(ApprovalTask.arrived_at.desc())
    total = db.scalar(select(func.count()).select_from(ApprovalTask).where(*filters)) or 0
    tasks = db.scalars(stmt.offset(paging.offset).limit(paging.page_size)).all()
    return PageResponse.create(items=[_response(task, task.records[-1].opinion if task.records else None) for task in tasks], total=total, params=paging)


@router.get("/todo", response_model=ApiResponse[PageResponse[ApprovalTaskResponse]])
def todo(
    request: Request, paging: PageParams = Depends(get_page_params), biz_type: str | None = None, applicant: str | None = None,
    arrived_from: date | None = Query(None, alias="arrived_from"), arrived_to: date | None = Query(None, alias="arrived_to"),
    db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("approval:task:view_todo")),
) -> ApiResponse[PageResponse[ApprovalTaskResponse]]:
    return ok(_list(db, user, resolve_current_room_id(request, db, user), ("pending",), paging, biz_type, applicant, None, False, arrived_from, arrived_to))


@router.get("/done", response_model=ApiResponse[PageResponse[ApprovalTaskResponse]])
def done(
    request: Request, paging: PageParams = Depends(get_page_params), biz_type: str | None = None, applicant: str | None = None,
    result: str | None = Query(None, pattern="^(approved|rejected)$"),
    arrived_from: date | None = Query(None, alias="arrived_from"), arrived_to: date | None = Query(None, alias="arrived_to"),
    db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user),
) -> ApiResponse[PageResponse[ApprovalTaskResponse]]:
    personal = not check_user_permission(db, user, "approval:record:view_done")
    return ok(_list(db, user, resolve_current_room_id(request, db, user), ("approved", "rejected"), paging, biz_type, applicant, result, personal, arrived_from, arrived_to))


def _act(task_id: int, payload: ApprovalActionRequest, action: str, request: Request, db: Session, user: SysUser) -> ApiResponse[ApprovalTaskResponse]:
    task = db.get(ApprovalTask, task_id)
    if task is None:
        raise NotFoundError(message="审批任务不存在")
    room_id = resolve_current_room_id(request, db, user)
    if task.org_unit_id != room_id:
        raise NotFoundError(message="审批任务不存在")
    latest_snapshot = task.records[-1].snapshot_json if task.records else {}
    record = complete_task(
        db, task_id, user.id, action=action, opinion=payload.opinion, snapshot=latest_snapshot,
        allow_room_approval=task.node_code == "director_approval",
    )
    if task.biz_type == "shift_swap" and task.node_code == "director_approval" and db.get(ShiftSwap, task.biz_id) is not None:
        director_decide(db, task.biz_id, user, approve=action == "approve", opinion=payload.opinion)
    db.commit()
    db.refresh(record.task)
    return ok(_response(record.task, record.opinion))


@router.post("/{task_id}/approve", response_model=ApiResponse[ApprovalTaskResponse])
def approve(task_id: int, payload: ApprovalActionRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("approval:task:view_todo"))) -> ApiResponse[ApprovalTaskResponse]:
    return _act(task_id, payload, "approve", request, db, user)


@router.post("/{task_id}/reject", response_model=ApiResponse[ApprovalTaskResponse])
def reject(task_id: int, payload: ApprovalActionRequest, request: Request, db: Session = Depends(get_db), user: SysUser = Depends(RequirePermission("approval:task:view_todo"))) -> ApiResponse[ApprovalTaskResponse]:
    return _act(task_id, payload, "reject", request, db, user)


@records_router.get("", response_model=ApiResponse[PageResponse[ApprovalRecordResponse]])
def list_records(
    request: Request, paging: PageParams = Depends(get_page_params), biz_type: str | None = None,
    db: Session = Depends(get_db), user: SysUser = Depends(get_authenticated_user),
) -> ApiResponse[PageResponse[ApprovalRecordResponse]]:
    room_id = resolve_current_room_id(request, db, user)
    filters = [_visibility_filter(user, room_id), ApprovalRecord.action.in_(("approve", "reject"))]
    if not check_user_permission(db, user, "approval:record:view_done"):
        filters.append(ApprovalTask.assignee_user_id == user.id)
    if biz_type:
        filters.append(ApprovalRecord.biz_type == biz_type)
    stmt = select(ApprovalRecord).join(ApprovalRecord.task).where(*filters).order_by(ApprovalRecord.operated_at.desc())
    total = db.scalar(select(func.count()).select_from(ApprovalRecord).join(ApprovalRecord.task).where(*filters)) or 0
    records = db.scalars(stmt.offset(paging.offset).limit(paging.page_size)).all()
    return ok(PageResponse.create(items=[ApprovalRecordResponse(
        id=record.id, task_id=record.task_id, biz_type=record.biz_type, biz_id=record.biz_id,
        action=record.action, opinion=record.opinion, operated_at=record.operated_at,
        snapshot=record.snapshot_json,
    ) for record in records], total=total, params=paging))
