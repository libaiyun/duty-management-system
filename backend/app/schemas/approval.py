from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApprovalActionRequest(BaseModel):
    opinion: str | None = Field(default=None, max_length=500)


class ApprovalTaskResponse(BaseModel):
    id: int
    biz_type: str
    biz_id: int
    node_code: str
    status: str
    arrived_at: datetime
    handled_at: datetime | None
    snapshot: dict[str, Any]
    opinion: str | None = None


class ApprovalRecordResponse(BaseModel):
    id: int
    task_id: int
    biz_type: str
    biz_id: int
    action: str
    opinion: str | None
    operated_at: datetime
    snapshot: dict[str, Any]
