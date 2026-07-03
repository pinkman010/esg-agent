from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from src.domain.enums import RunStatus


class ReportUploadResponse(BaseModel):
    report_id: str
    original_filename: str
    file_hash: str
    status: Literal["uploaded"]


class AnalyzeResponse(BaseModel):
    run_id: str
    report_id: str
    status: RunStatus
    confirm_llm: bool
    error_message: str | None = None


class AuditEvent(BaseModel):
    audit_event_id: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime | None = None


class AuditRun(BaseModel):
    run_id: str
    report_id: str
    original_filename: str
    file_hash: str
    status: RunStatus
    model_called: bool
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    events: list[AuditEvent]

