from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, model_validator

from src.db.repositories import Repository
from src.db.session import get_db_session
from src.config.settings import get_settings
from src.api.schemas import ExportVersionResponse
from src.services.export_service import (
    ExportFileIntegrityError,
    ExportFileNotFoundError,
    ExportGateError,
    VersionedExportService,
    assessments_rows,
    public_export_manifest,
    resolve_export_file,
    review_rows,
    rows_to_csv,
)

router = APIRouter(prefix="/api/exports", tags=["exports"])
report_export_router = APIRouter(prefix="/api/reports/{report_id}/exports", tags=["exports"])


class GenerateExportRequest(BaseModel):
    formats: list[str] = Field(min_length=1)
    created_by: str

    @model_validator(mode="after")
    def validate_unique_formats(self):
        if len(self.formats) != len(set(self.formats)):
            raise ValueError("formats must not contain duplicates")
        return self


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


def _public_export(export) -> dict:
    payload = export.model_dump(mode="json")
    payload["file_manifest"] = public_export_manifest(export)
    return payload


@report_export_router.get("", response_model=list[ExportVersionResponse])
def list_versions(report_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    return [
        _public_export(item)
        for item in Repository(session).list_export_versions(report_id)
    ]


def _generate(report_id: str, request: GenerateExportRequest, session: Session, *, is_draft: bool) -> dict:
    service = VersionedExportService(Repository(session), get_settings().derived_dir)
    try:
        result = service.generate(report_id, is_draft=is_draft, formats=request.formats, created_by=request.created_by)
    except ExportGateError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "remaining": exc.remaining},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _public_export(result)


@report_export_router.post("/draft", response_model=ExportVersionResponse)
def generate_draft(report_id: str, request: GenerateExportRequest, session: Session = Depends(get_db_session)) -> dict:
    return _generate(report_id, request, session, is_draft=True)


@report_export_router.post("/formal", response_model=ExportVersionResponse)
def generate_formal(report_id: str, request: GenerateExportRequest, session: Session = Depends(get_db_session)) -> dict:
    return _generate(report_id, request, session, is_draft=False)


@router.get("/{export_id}/files/{file_id}")
def download_export_file(
    export_id: str,
    file_id: str,
    session: Session = Depends(get_db_session),
) -> FileResponse:
    repository = Repository(session)
    export = repository.get_export_version(export_id)
    if export is None:
        raise HTTPException(status_code=404, detail="export_not_found")
    try:
        resolved = resolve_export_file(
            export,
            file_id,
            output_root=get_settings().derived_dir,
        )
    except ExportFileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="export_file_not_found",
        ) from None
    except ExportFileIntegrityError:
        raise HTTPException(
            status_code=409,
            detail="export_file_integrity_mismatch",
        ) from None

    media_types = {
        "assessment_xlsx": (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        "management_pdf": "application/pdf",
        "print_html": "text/html; charset=utf-8",
    }
    repository.create_audit_event(
        export.run_id,
        "export_file_downloaded",
        {
            "export_id": export.export_id,
            "file_id": file_id,
            "format": resolved.format,
            "size": resolved.size,
            "sha256": resolved.sha256,
        },
    )
    return FileResponse(
        resolved.path,
        media_type=media_types.get(
            resolved.format,
            "application/octet-stream",
        ),
        filename=resolved.filename,
    )
