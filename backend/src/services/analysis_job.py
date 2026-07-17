import logging

from src.config.settings import get_settings
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.domain.enums import ReportStatus, RunStatus
from src.domain.models import AnalysisStageEvent
from src.services.analysis_runner import execute_analysis


logger = logging.getLogger(__name__)

INTERRUPTED_ANALYSIS_REASON = "分析服务重启，任务已中断"


def _persist_analysis_failure(
    repository: Repository,
    *,
    report_id: str,
    run_id: str,
    error_message: str,
    audit_event_type: str = "analysis_failed",
) -> None:
    repository.append_analysis_stage_event(
        AnalysisStageEvent(
            run_id=run_id,
            stage_code="result_summary",
            status="failed",
            completed_units=0,
            total_units=1,
            error_summary=error_message,
        )
    )
    repository.create_audit_event(
        run_id,
        audit_event_type,
        {"report_id": report_id, "error": error_message},
    )
    repository.update_report_status(report_id, ReportStatus.ANALYSIS_FAILED)
    repository.update_run_status(
        run_id,
        RunStatus.FAILED,
        error_message=error_message,
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
