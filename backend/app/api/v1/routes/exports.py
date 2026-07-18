from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import RequirePermission, get_db, get_page_params, resolve_current_room_id
from app.core.exceptions import BusinessRuleError, NotFoundError, StateConflictError
from app.models.export import ExportTask
from app.models.schedule import MonthlySchedule
from app.models.user import SysUser
from app.schemas.export import ExportTaskResponse, ScheduleExportRequest
from app.schemas.pagination import PageParams, PageResponse
from app.schemas.response import ApiResponse, ok
from app.services.export import create_schedule_export

router = APIRouter(prefix="/exports", tags=["exports"])


def _response(task: ExportTask) -> ExportTaskResponse:
    return ExportTaskResponse(
        id=task.id,
        task_type=task.task_type,
        status=task.status,
        year_month=task.year_month,
        file_name=task.file_name,
        error_message=task.error_message,
        created_at=task.created_at,
    )


@router.post("/schedule", response_model=ApiResponse[ExportTaskResponse])
def create_schedule_export_endpoint(
    payload: ScheduleExportRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("schedule:monthly:generate")),
) -> ApiResponse[ExportTaskResponse]:
    room_id = resolve_current_room_id(request, db, user)
    schedule = db.get(MonthlySchedule, payload.schedule_id)
    if schedule is None or schedule.org_unit_id != room_id:
        raise NotFoundError(message="排班记录不存在")
    if schedule.status != "published":
        raise BusinessRuleError(message="仅已发布排班可导出")
    task = ExportTask(
        org_unit_id=room_id,
        task_type="schedule",
        status="pending",
        year_month=f"{payload.year:04d}-{payload.month:02d}",
        created_by=user.id,
    )
    db.add(task)
    db.flush()
    task = create_schedule_export(
        db, task, schedule, payload.year, payload.month, request.app.state.settings.export_dir
    )
    db.commit()
    db.refresh(task)
    if task.status == "failed":
        raise BusinessRuleError(message=task.error_message or "导出失败")
    return ok(_response(task))


@router.get("", response_model=ApiResponse[PageResponse[ExportTaskResponse]])
def list_export_tasks_endpoint(
    request: Request,
    paging: PageParams = Depends(get_page_params),
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("export:task:view")),
) -> ApiResponse[PageResponse[ExportTaskResponse]]:
    room_id = resolve_current_room_id(request, db, user)
    stmt = select(ExportTask).where(ExportTask.org_unit_id == room_id).order_by(ExportTask.created_at.desc())
    total = db.scalar(select(func.count()).select_from(ExportTask).where(ExportTask.org_unit_id == room_id)) or 0
    tasks = db.scalars(stmt.offset(paging.offset).limit(paging.page_size)).all()
    return ok(PageResponse.create(items=[_response(task) for task in tasks], total=total, params=paging))


@router.get("/{task_id}/download")
def download_export_endpoint(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: SysUser = Depends(RequirePermission("export:task:view")),
) -> FileResponse:
    task = db.get(ExportTask, task_id)
    if task is None or task.org_unit_id != resolve_current_room_id(request, db, user):
        raise NotFoundError(message="导出任务不存在")
    if task.status != "completed" or not task.file_path or not task.file_name:
        raise StateConflictError(message="导出文件尚未生成")
    file_name = Path(task.file_path).name
    if file_name != task.file_path:
        raise NotFoundError(message="导出文件不存在")
    path = Path(request.app.state.settings.export_dir) / file_name
    if not path.is_file():
        raise NotFoundError(message="导出文件不存在")
    return FileResponse(
        path, filename=task.file_name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
