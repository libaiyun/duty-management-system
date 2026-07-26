from typing import Any, cast

from sqlalchemy import select, true, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError, StateConflictError
from app.models.approval import ApprovalRecord, ApprovalTask
from app.models.base import _utcnow


def create_task(
    db: Session, *, biz_type: str, biz_id: int, node_code: str, assignee_user_id: int,
    org_unit_id: int, snapshot: dict[str, Any], created_by: int | None = None,
) -> ApprovalTask:
    task = ApprovalTask(
        biz_type=biz_type, biz_id=biz_id, node_code=node_code, assignee_user_id=assignee_user_id,
        org_unit_id=org_unit_id, created_by=created_by,
    )
    db.add(task)
    db.flush()
    db.add(ApprovalRecord(task_id=task.id, biz_type=biz_type, biz_id=biz_id, action="submit", operator_user_id=created_by or assignee_user_id, snapshot_json=snapshot, created_by=created_by))
    db.flush()
    return task


def complete_task(
    db: Session, task_id: int, operator_user_id: int, *, action: str, opinion: str | None,
    snapshot: dict[str, Any], allow_room_approval: bool = False,
) -> ApprovalRecord:
    if action not in {"approve", "reject"}:
        raise StateConflictError(message="不支持的审批动作")
    if action == "reject" and not (opinion or "").strip():
        raise BusinessRuleError(message="拒绝时必须填写审批意见")
    status = "approved" if action == "approve" else "rejected"
    assignee_filter = true() if allow_room_approval else ApprovalTask.assignee_user_id == operator_user_id
    result = cast(CursorResult[Any], db.execute(
        update(ApprovalTask).where(
            ApprovalTask.id == task_id, assignee_filter,
            ApprovalTask.status == "pending",
        ).values(status=status, handled_at=_utcnow(), updated_by=operator_user_id, version=ApprovalTask.version + 1)
    ))
    if result.rowcount != 1:
        task = db.scalar(select(ApprovalTask).where(ApprovalTask.id == task_id))
        if task is None:
            raise NotFoundError(message="审批任务不存在")
        if not allow_room_approval and task.assignee_user_id != operator_user_id:
            raise ForbiddenError(message="无审批权限")
        raise StateConflictError(message="该审批任务已处理")
    task = db.get(ApprovalTask, task_id)
    assert task is not None
    record = ApprovalRecord(
        task_id=task.id, biz_type=task.biz_type, biz_id=task.biz_id, action=action,
        operator_user_id=operator_user_id, opinion=opinion, snapshot_json=snapshot, created_by=operator_user_id,
    )
    db.add(record)
    db.flush()
    return record


def cancel_pending_tasks(
    db: Session, *, biz_type: str, biz_id: int, operator_user_id: int,
) -> None:
    """Close outstanding workflow tasks when their business document is withdrawn.

    A withdrawn document must not remain in the approval centre's todo list.
    Keeping a cancellation record also preserves the workflow trail without
    treating the document as approved or rejected.
    """
    tasks = list(db.scalars(
        select(ApprovalTask)
        .where(
            ApprovalTask.biz_type == biz_type,
            ApprovalTask.biz_id == biz_id,
            ApprovalTask.status == "pending",
        )
        .with_for_update()
    ).all())
    for task in tasks:
        task.status = "cancelled"
        task.handled_at = _utcnow()
        task.updated_by = operator_user_id
        task.version += 1
        snapshot = task.records[-1].snapshot_json if task.records else {}
        db.add(ApprovalRecord(
            task_id=task.id,
            biz_type=task.biz_type,
            biz_id=task.biz_id,
            action="cancel",
            operator_user_id=operator_user_id,
            snapshot_json=snapshot,
            created_by=operator_user_id,
        ))
    db.flush()
