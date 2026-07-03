from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.repositories import Repository
from src.db.session import get_db_session
from src.domain.models import AnalysisRun, DisclosureAssessment, Recommendation

router = APIRouter(prefix="/api/runs", tags=["runs"])


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
