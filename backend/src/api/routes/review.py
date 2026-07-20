from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.repositories import Repository
from src.db.session import get_db_session
from src.domain.enums import ApplicabilityStatus, AssessmentVerdict, ReviewOperation, ReviewStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, ReviewDecision, ReviewSnapshot
from src.services.review_service import ReviewService

router = APIRouter(prefix="/api/review", tags=["review"])
assessment_router = APIRouter(prefix="/api/assessments", tags=["review"])
report_router = APIRouter(prefix="/api/reports", tags=["review"])


class ReviewDecisionRequest(BaseModel):
    assessment_id: str
    review_status: ReviewStatus
    reviewer_note: str = ""


class ReviewSnapshotRequest(BaseModel):
    operation_type: ReviewOperation
    reviewer_name: str
    reason_code: str
    reviewer_note: str = ""
    reviewed_verdict: AssessmentVerdict | None = None
    reviewed_applicability_status: ApplicabilityStatus | None = None
    evidence_pages: list[int] | None = None
    evidence_preview: str | None = None
    rationale: str | None = None
    missing_items: list[str] | None = None
    expected_previous_snapshot_id: str | None = None


class ApplicabilityBatchReviewRequest(BaseModel):
    assessment_ids: list[str] = Field(min_length=1, max_length=100)
    reviewed_applicability_status: ApplicabilityStatus
    reviewer_name: str = Field(min_length=1)
    reviewer_note: str = Field(min_length=1)


class ApplicabilityBatchReviewResponse(BaseModel):
    batch_id: str
    updated_count: int
    assessment_ids: list[str]


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


@assessment_router.post("/{assessment_id}/review-decisions", response_model=ReviewSnapshot)
def save_review_snapshot(
    assessment_id: str,
    request: ReviewSnapshotRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    service = ReviewService(Repository(session))
    try:
        snapshot = service.record(assessment_id, **request.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return dump_model(snapshot)


@assessment_router.get("/{assessment_id}/review-history", response_model=list[ReviewSnapshot])
def review_history(assessment_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    repo = Repository(session)
    if repo.get_assessment(assessment_id) is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    return [dump_model(snapshot) for snapshot in repo.list_review_snapshots(assessment_id)]


@report_router.post(
    "/{report_id}/applicability-decisions",
    response_model=ApplicabilityBatchReviewResponse,
)
def save_applicability_batch_review(
    report_id: str,
    request: ApplicabilityBatchReviewRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    service = ReviewService(Repository(session))
    try:
        batch_id, snapshots = service.record_applicability_batch(
            report_id,
            **request.model_dump(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "batch_id": batch_id,
        "updated_count": len(snapshots),
        "assessment_ids": [item.assessment_id for item in snapshots],
    }
