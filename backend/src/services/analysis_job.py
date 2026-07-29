import logging
import re

from src.config.settings import get_settings
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.domain.enums import RunStatus
from src.domain.models import AnalysisStageEvent
from src.services.analysis_runner import (
    execute_analysis,
    resolve_effective_report_status,
)


logger = logging.getLogger(__name__)

INTERRUPTED_ANALYSIS_REASON = "分析服务重启，任务已中断"
_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:\\[^\s]+")
_CONNECTION_URL = re.compile(
    r"(?i)\b(?:postgresql|postgres|mysql|mariadb|mongodb|redis)://[^\s]+"
)
_BEARER_TOKEN = re.compile(r"(?i)authorization:\s*bearer\s+[^\s]+")
_NAMED_SECRET = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[^\s]+"
)
_MAX_SAFE_ERROR_LENGTH = 500


def safe_analysis_error(error_message: str) -> str:
    message = " ".join(str(error_message).split())
    message = _WINDOWS_PATH.sub("[path redacted]", message)
    message = _CONNECTION_URL.sub("[connection redacted]", message)
    message = _BEARER_TOKEN.sub("Authorization: Bearer [redacted]", message)
    message = _NAMED_SECRET.sub("[secret redacted]", message)
    if len(message) > _MAX_SAFE_ERROR_LENGTH:
        return message[: _MAX_SAFE_ERROR_LENGTH - 3] + "..."
    return message


def _persist_analysis_failure(
    repository: Repository,
    *,
    report_id: str,
    run_id: str,
    error_message: str,
    audit_event_type: str = "analysis_failed",
    error_code: str = "analysis_execution_failed",
) -> None:
    safe_error_message = safe_analysis_error(error_message)
    run = repository.get_run(run_id)
    if run is None:
        raise ValueError(f"run not found: {run_id}")
    failure_summary = dict(run.failure_summary)
    retry_ids = failure_summary.get("retry_requirement_ids", [])
    if (
        isinstance(retry_ids, list)
        and retry_ids
        and not failure_summary.get("failed_requirement_ids")
    ):
        failure_summary["failed_requirement_ids"] = retry_ids
    failure_summary["error_code"] = error_code
    updated_run = repository.update_run_status(
        run_id,
        RunStatus.FAILED,
        error_message=safe_error_message,
        failed_requirement_count=len(
            failure_summary.get("failed_requirement_ids", [])
        ),
        failure_summary=failure_summary,
    )
    repository.append_analysis_stage_event(
        AnalysisStageEvent(
            run_id=run_id,
            stage_code="result_summary",
            status="failed",
            completed_units=0,
            total_units=1,
            error_summary=safe_error_message,
        )
    )
    repository.create_audit_event(
        run_id,
        audit_event_type,
        {
            "report_id": report_id,
            "error_code": error_code,
            "error": safe_error_message,
        },
    )
    repository.update_report_status(
        report_id,
        resolve_effective_report_status(
            repository,
            report_id=report_id,
            run_result=updated_run,
        ),
    )


def execute_analysis_job(
    *,
    report_id: str,
    run_id: str,
    confirm_llm: bool,
    enable_ocr: bool = False,
    ocr_pages: list[int] | None = None,
    requirement_ids: set[str] | None = None,
) -> None:
    session = SessionLocal()
    repository = Repository(session)
    try:
        report = repository.get_report(report_id)
        if report is None:
            raise ValueError(f"report not found: {report_id}")
        execute_analysis(
            repository,
            report,
            get_settings(),
            run_id=run_id,
            confirm_llm=confirm_llm,
            enable_ocr=enable_ocr,
            ocr_pages=ocr_pages,
            requirement_ids=requirement_ids,
        )
    except Exception as exc:
        repository.rollback()
        try:
            _persist_analysis_failure(
                repository,
                report_id=report_id,
                run_id=run_id,
                error_message=str(exc),
            )
        except Exception:
            repository.rollback()
            logger.critical(
                "analysis job failure state could not be persisted (report_id=%s, run_id=%s)",
                report_id,
                run_id,
            )
            raise
        logger.error(
            "analysis job failed and was marked terminal (report_id=%s, run_id=%s)",
            report_id,
            run_id,
        )
    finally:
        session.close()


def recover_interrupted_analysis_runs() -> int:
    session = SessionLocal()
    repository = Repository(session)
    try:
        active_runs = repository.list_active_runs()
        for run in active_runs:
            _persist_analysis_failure(
                repository,
                report_id=run.report_id,
                run_id=run.run_id,
                error_message=INTERRUPTED_ANALYSIS_REASON,
                audit_event_type="analysis_interrupted_by_restart",
                error_code="analysis_interrupted_by_restart",
            )
        if active_runs:
            logger.warning("recovered %d interrupted analysis run(s)", len(active_runs))
        return len(active_runs)
    except Exception:
        repository.rollback()
        logger.critical("interrupted analysis recovery failed")
        raise
    finally:
        session.close()
