from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.schemas import AuditRun, ReportAuditListResponse
from src.db.repositories import Repository
from src.db.session import get_db_session
from src.services.audit_projection_service import (
    sanitize_audit_payload,
    sanitize_audit_text,
)

router = APIRouter(prefix="/api/audit", tags=["audit"])
report_router = APIRouter(
    prefix="/api/reports/{report_id}",
    tags=["audit"],
)


@router.get("/runs", response_model=list[AuditRun])
def list_audit_runs(session: Session = Depends(get_db_session)) -> list[dict]:
    runs = Repository(session).list_audit_runs()
    return [
        {
            **run,
            "error_message": (
                sanitize_audit_text(run["error_message"])
                if run["error_message"]
                else None
            ),
            "events": [
                {
                    **event,
                    "payload": sanitize_audit_payload(event["payload"]),
                }
                for event in run["events"]
            ],
        }
        for run in runs
    ]


@report_router.get("/audit", response_model=ReportAuditListResponse)
def list_report_audit(
    report_id: str,
    event_type: str | None = Query(default=None, min_length=1, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> dict:
    repository = Repository(session)
    if repository.get_report(report_id) is None:
        raise HTTPException(status_code=404, detail="report not found")
    total, records = repository.list_report_audit_events(
        report_id,
        event_type=event_type,
        offset=offset,
        limit=limit,
    )
    return {
        "items": [
            {
                "audit_event_id": record.audit_event_id,
                "run_id": record.run_id,
                "event_type": record.event_type,
                "payload": sanitize_audit_payload(record.event_payload),
                "created_at": record.created_at,
            }
            for record in records
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
