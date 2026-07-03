from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.db.repositories import Repository
from src.db.session import get_db_session
from src.services.export_service import assessments_rows, review_rows, rows_to_csv

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/runs/{run_id}/assessments.json")
def export_assessments_json(run_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    repository = Repository(session)
    rows = assessments_rows(repository, run_id)
    repository.create_audit_event(run_id, "assessments_json_exported", {"row_count": len(rows)})
    return rows


@router.get("/runs/{run_id}/assessments.csv")
def export_assessments_csv(run_id: str, session: Session = Depends(get_db_session)) -> PlainTextResponse:
    repository = Repository(session)
    rows = assessments_rows(repository, run_id)
    repository.create_audit_event(run_id, "assessments_csv_exported", {"row_count": len(rows)})
    return PlainTextResponse(rows_to_csv(rows), media_type="text/csv")


@router.get("/runs/{run_id}/review.json")
def export_review_json(run_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    repository = Repository(session)
    rows = review_rows(repository, run_id)
    repository.create_audit_event(run_id, "review_json_exported", {"row_count": len(rows)})
    return rows


@router.get("/runs/{run_id}/review.csv")
def export_review_csv(run_id: str, session: Session = Depends(get_db_session)) -> PlainTextResponse:
    repository = Repository(session)
    rows = review_rows(repository, run_id)
    repository.create_audit_event(run_id, "review_csv_exported", {"row_count": len(rows)})
    return PlainTextResponse(rows_to_csv(rows), media_type="text/csv")
