from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.repositories import Repository
from src.db.session import get_db_session
from src.domain.enums import ReportStatus
from src.services.analysis_job import execute_analysis_job
from src.api.schemas import AnalysisStageResponse
from src.domain.models import AnalysisRun, AnalysisStageEvent, DisclosureAssessment, Recommendation

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RetryFailedRequest(BaseModel):
    reason: str


def dump_model(model):
    return model.model_dump(mode="json")


@router.get("", response_model=list[AnalysisRun])
def list_runs(session: Session = Depends(get_db_session)) -> list[dict]:
    return [dump_model(run) for run in Repository(session).list_runs()]


@router.get("/{run_id}", response_model=AnalysisRun)
def get_run(run_id: str, session: Session = Depends(get_db_session)) -> dict:
    run = Repository(session).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return dump_model(run)


@router.get("/{run_id}/assessments", response_model=list[DisclosureAssessment])
def list_assessments(run_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    return [dump_model(assessment) for assessment in Repository(session).list_assessments_by_run(run_id)]


@router.get("/{run_id}/recommendations", response_model=list[Recommendation])
def list_recommendations(run_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    return [dump_model(recommendation) for recommendation in Repository(session).list_recommendations_by_run(run_id)]


@router.get("/{run_id}/stages", response_model=list[AnalysisStageResponse])
def list_stages(run_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    repo = Repository(session)
    if repo.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    return [
        stage.model_dump(
            mode="json",
            include={"stage_code", "status", "completed_units", "total_units", "error_summary", "created_at"},
        )
        for stage in repo.list_latest_analysis_stages(run_id)
    ]


@router.post("/{run_id}/retry-failed", response_model=AnalysisRun)
def retry_failed(
    run_id: str,
    request: RetryFailedRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
) -> dict:
    repo = Repository(session)
    try:
        run = repo.create_retry_run(run_id, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    report = repo.get_report(run.report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    requirement_ids = set(run.failure_summary["retry_requirement_ids"])
    repo.update_report_status(report.report_id, ReportStatus.ANALYZING)
    background_tasks.add_task(
        execute_analysis_job,
        report_id=report.report_id,
        run_id=run.run_id,
        confirm_llm=run.confirm_llm,
        requirement_ids=requirement_ids,
    )
    return dump_model(run)
