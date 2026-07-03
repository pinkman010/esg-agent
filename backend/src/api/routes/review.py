from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.repositories import Repository
from src.db.session import get_db_session
from src.domain.enums import ReviewStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, ReviewDecision

router = APIRouter(prefix="/api/review", tags=["review"])


class ReviewDecisionRequest(BaseModel):
    assessment_id: str
    review_status: ReviewStatus
    reviewer_note: str = ""


def dump_model(model):
    return model.model_dump(mode="json")


@router.get("/runs", response_model=list[AnalysisRun])
def list_review_runs(session: Session = Depends(get_db_session)) -> list[dict]:
    return [dump_model(run) for run in Repository(session).list_review_runs()]


@router.get("/runs/{run_id}/assessments", response_model=list[DisclosureAssessment])
def list_review_assessments(run_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    assessments = Repository(session).list_assessments_by_run(run_id)
    return [
        dump_model(assessment)
        for assessment in assessments
        if assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    ]


@router.post("/runs/{run_id}/decisions", response_model=ReviewDecision)
def save_review_decision(
    run_id: str,
    request: ReviewDecisionRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    repository = Repository(session)
    decision = repository.save_review_decision(
        ReviewDecision(
            decision_id=f"decision-{uuid4().hex}",
            run_id=run_id,
            assessment_id=request.assessment_id,
            review_status=request.review_status,
            reviewer_note=request.reviewer_note,
        )
    )
    repository.create_audit_event(
        run_id,
        "review_decision_saved",
        {"decision_id": decision.decision_id, "assessment_id": request.assessment_id},
    )
    return dump_model(decision)
