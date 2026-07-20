from io import BytesIO
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.schemas import AnalyzeResponse, ConfirmReportMetadataRequest, ReportListResponse, ReportResponse, ReportUploadResponse
from src.config.environment_safety import validate_demo_environment
from src.config.settings import get_settings
from src.db.repositories import ReportMetadataLockedError, Repository
from src.db.session import get_db_session
from src.domain.enums import ReportStatus, RunStatus
from src.domain.models import AnalysisRun, Report
from src.domain.versions import CURRENT_RISK_RULE_VERSION
from src.services.document_store import DocumentStore
from src.services.metadata_detection import detect_report_metadata
from src.services.analysis_job import execute_analysis_job

router = APIRouter(prefix="/api/reports", tags=["reports"])


class AnalyzeRequest(BaseModel):
    confirm_llm: bool = False
    enable_ocr: bool = False
    ocr_pages: list[int] = []


def _can_start_new_demo(session: Session) -> bool:
    settings = get_settings()
    try:
        validate_demo_environment(
            app_env=settings.app_env,
            database_url=settings.database_url,
            upload_dir=settings.upload_dir,
            derived_dir=settings.derived_dir,
        )
    except ValueError:
        return False
    return session.scalar(text("SELECT current_database()")) == "esg_agent_demo"


def _report_response(report: Report) -> dict:
    return report.model_dump(exclude={"stored_path", "reopened_at", "reopen_reason"})


@router.get("", response_model=ReportListResponse)
def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    status: ReportStatus | None = None,
    session: Session = Depends(get_db_session),
) -> dict:
    reports, total = Repository(session).list_reports(page=page, page_size=page_size, status=status)
    return {"items": [_report_response(report) for report in reports], "page": page, "page_size": page_size, "total": total}


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, session: Session = Depends(get_db_session)) -> dict:
    report = Repository(session).get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return _report_response(report)


@router.get("/{report_id}/file")
def get_report_file(report_id: str, session: Session = Depends(get_db_session)):
    report = Repository(session).get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    path = Path(report.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="report file not found")
    return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": "inline"})


@router.post("/upload", response_model=ReportUploadResponse)
async def upload_report(
    file: UploadFile = File(...),
    duplicate_policy: Literal["reject", "create_new"] = Query(default="reject"),
    session: Session = Depends(get_db_session),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    content = await file.read()
    file_hash = sha256(content).hexdigest()
    repo = Repository(session)
    existing = repo.find_report_by_hash(file_hash)
    if existing is not None and duplicate_policy == "reject":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_report",
                "message": "相同报告已存在",
                "report_id": existing.report_id,
                "existing_report_status": existing.status.value,
                "can_start_new_demo": _can_start_new_demo(session),
            },
        )

    settings = get_settings()
    store = DocumentStore(upload_dir=settings.upload_dir, derived_dir=settings.derived_dir)
    saved = store.save_upload(BytesIO(content), file.filename)
    detected = detect_report_metadata(file.filename, content)
    report_id = f"report-{uuid4().hex}"
    repo.create_report(
        Report(
            report_id=report_id,
            original_filename=saved.original_filename,
            stored_path=saved.stored_path,
            file_hash=saved.file_hash,
            page_count=detected.page_count,
            status=ReportStatus.UPLOADED,
            metadata_detected=detected.metadata,
        )
    )
    audit_payload = {"report_id": report_id, "file_hash": saved.file_hash}
    if existing is not None:
        audit_payload["duplicate_of_report_id"] = existing.report_id
    repo.create_audit_event(None, "report_uploaded", audit_payload)
    return {
        "report_id": report_id,
        "original_filename": saved.original_filename,
        "file_hash": saved.file_hash,
        "status": "uploaded",
    }


@router.post("/{report_id}/confirm-metadata", response_model=ReportResponse)
def confirm_report_metadata(
    report_id: str,
    request: ConfirmReportMetadataRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    repo = Repository(session)
    try:
        report = repo.confirm_report_metadata(
            report_id,
            company_name=request.company_name.strip(),
            report_year=request.report_year,
            language=request.language.strip(),
        )
    except ReportMetadataLockedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "report_metadata_locked", "message": "报告已进入分析流程"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="report not found") from exc
    repo.create_audit_event(None, "report_metadata_confirmed", {"report_id": report_id})
    return _report_response(report)


@router.post("/{report_id}/analyze", response_model=AnalyzeResponse)
def analyze_report(
    report_id: str,
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
) -> dict:
    repo = Repository(session)
    report = repo.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    active_run = repo.get_active_run_for_report(report_id)
    if active_run is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "analysis_already_running", "run_id": active_run.run_id},
        )
    if report.status is not ReportStatus.READY_FOR_ANALYSIS:
        raise HTTPException(
            status_code=409,
            detail={"code": "report_not_ready", "message": "报告信息尚未确认"},
        )

    try:
        run = repo.create_run(
            AnalysisRun(
                run_id=f"run-{uuid4().hex}",
                report_id=report_id,
                status=RunStatus.PENDING,
                confirm_llm=request.confirm_llm,
                risk_rule_version=CURRENT_RISK_RULE_VERSION,
                eligible_requirement_count=577,
            )
        )
    except ValueError as exc:
        active_run = repo.get_active_run_for_report(report_id)
        raise HTTPException(
            status_code=409,
            detail={"code": "analysis_already_running", "run_id": active_run.run_id if active_run else None},
        ) from exc
    repo.update_report_status(report_id, ReportStatus.ANALYZING)
    background_tasks.add_task(
        execute_analysis_job,
        report_id=report_id,
        run_id=run.run_id,
        confirm_llm=request.confirm_llm,
        enable_ocr=request.enable_ocr,
        ocr_pages=request.ocr_pages,
    )
    return {
        "run_id": run.run_id,
        "report_id": run.report_id,
        "status": run.status.value,
        "confirm_llm": run.confirm_llm,
        "error_message": run.error_message,
    }
