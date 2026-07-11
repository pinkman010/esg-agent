from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.db.repositories import Repository
from src.db.session import get_db_session
from src.config.settings import get_settings
from src.domain.models import ExportVersion
from src.services.export_service import VersionedExportService, assessments_rows, review_rows, rows_to_csv

router = APIRouter(prefix="/api/exports", tags=["exports"])
report_export_router = APIRouter(prefix="/api/reports/{report_id}/exports", tags=["exports"])


class GenerateExportRequest(BaseModel):
    formats: list[str]
    created_by: str


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


@report_export_router.get("", response_model=list[ExportVersion])
def list_versions(report_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    return [item.model_dump(mode="json") for item in Repository(session).list_export_versions(report_id)]


def _generate(report_id: str, request: GenerateExportRequest, session: Session, *, is_draft: bool) -> dict:
    service = VersionedExportService(Repository(session), get_settings().derived_dir)
    try:
        result = service.generate(report_id, is_draft=is_draft, formats=request.formats, created_by=request.created_by)
    except PermissionError as exc:
        remaining = int(str(exc).rsplit(":", 1)[-1].strip())
        raise HTTPException(status_code=409, detail={"code": "high_risk_review_incomplete", "remaining": remaining}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@report_export_router.post("/draft", response_model=ExportVersion)
def generate_draft(report_id: str, request: GenerateExportRequest, session: Session = Depends(get_db_session)) -> dict:
    return _generate(report_id, request, session, is_draft=True)


@report_export_router.post("/formal", response_model=ExportVersion)
def generate_formal(report_id: str, request: GenerateExportRequest, session: Session = Depends(get_db_session)) -> dict:
    return _generate(report_id, request, session, is_draft=False)
