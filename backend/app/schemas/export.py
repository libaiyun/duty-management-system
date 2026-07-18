from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleExportRequest(BaseModel):
    schedule_id: int
    year: int = Field(ge=1, le=9999)
    month: int = Field(ge=1, le=12)


class ExportTaskResponse(BaseModel):
    id: int
    task_type: str
    status: str
    year_month: str
    file_name: str | None
    error_message: str | None
    created_at: datetime
