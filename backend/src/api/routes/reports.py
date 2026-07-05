from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.disclosure_agent import DisclosureAgent
from src.api.schemas import AnalyzeResponse, ReportUploadResponse
from src.config.settings import get_settings
from src.db.repositories import Repository
from src.db.session import get_db_session
from src.domain.models import Report
from src.services.document_parser import DocumentParser
from src.services.document_store import DocumentStore
from src.services.ocr import run_ocr_for_pages
from src.standards.gri import GRIAdapter
from src.workflows.single_report_workflow import SingleReportWorkflow

router = APIRouter(prefix="/api/reports", tags=["reports"])
GRI_REQUIREMENTS_PATH = Path(__file__).resolve().parents[3] / "data" / "manifests" / "gri_requirement_checklist.json"
GRI_REQUIREMENT_PACK_PATH = Path(__file__).resolve().parents[3] / "data" / "manifests" / "gri_requirement_pack.json"
GRI_REQUIREMENTS_LIMIT = 10


class AnalyzeRequest(BaseModel):
    confirm_llm: bool = False
    enable_ocr: bool = False
    ocr_pages: list[int] = []


@router.post("/upload", response_model=ReportUploadResponse)
async def upload_report(file: UploadFile = File(...), session: Session = Depends(get_db_session)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    settings = get_settings()
    store = DocumentStore(upload_dir=settings.upload_dir, derived_dir=settings.derived_dir)
    saved = store.save_upload(BytesIO(await file.read()), file.filename)
    report_id = f"report-{uuid4().hex}"
    repo = Repository(session)
    repo.create_report(
        Report(
            report_id=report_id,
            original_filename=saved.original_filename,
            stored_path=saved.stored_path,
            file_hash=saved.file_hash,
        )
    )
    repo.create_audit_event(None, "report_uploaded", {"report_id": report_id, "file_hash": saved.file_hash})
    return {
        "report_id": report_id,
        "original_filename": saved.original_filename,
        "file_hash": saved.file_hash,
        "status": "uploaded",
    }


@router.post("/{report_id}/analyze", response_model=AnalyzeResponse)
def analyze_report(report_id: str, request: AnalyzeRequest, session: Session = Depends(get_db_session)) -> dict:
    repo = Repository(session)
    report = repo.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    settings = get_settings()

    def ocr_runner(pdf_path: Path, pages: list[int]):
        return run_ocr_for_pages(
            pdf_path,
            pages,
            report_id=report_id,
            derived_dir=settings.derived_dir,
            ocrmypdf_cmd=settings.ocrmypdf_cmd,
            tesseract_cmd=settings.tesseract_cmd,
            ocr_lang=settings.ocr_lang,
        )

    workflow = SingleReportWorkflow(
        repo,
        DocumentParser(ocr_runner=ocr_runner),
        GRIAdapter(GRI_REQUIREMENTS_PATH, max_requirements=GRI_REQUIREMENTS_LIMIT),
        DisclosureAgent(),
        requirement_pack_path=GRI_REQUIREMENT_PACK_PATH,
        ocr_max_pages=settings.ocr_max_pages,
    )
    run = workflow.run(
        report_id,
        Path(report.stored_path),
        report.file_hash,
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
