from pathlib import Path

from src.agents.disclosure_agent import DisclosureAgent
from src.config.settings import Settings
from src.db.repositories import Repository
from src.domain.enums import ReportStatus, RunStatus
from src.domain.models import AnalysisRun, Report
from src.services.document_parser import DocumentParser
from src.services.ai_assessment_service import AIAssessmentService
from src.services.ocr import run_ocr_for_pages
from src.standards.gri import GRIAdapter
from src.workflows.single_report_workflow import SingleReportWorkflow
from src.tools.llm_client import LLMClient


DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
GRI_REQUIREMENTS_PATH = DATA_ROOT / "manifests" / "gri_requirement_checklist_v2.json"
GRI_REQUIREMENT_PACK_PATH = DATA_ROOT / "manifests" / "gri_requirement_pack.json"
ENVISION_2024_PROFILE_PATH = DATA_ROOT / "reports" / "profiles" / "envision_2024.json"
GRI_REQUIREMENTS_LIMIT = None


def execute_analysis(
    repo: Repository,
    report: Report,
    settings: Settings,
    *,
    run_id: str,
    confirm_llm: bool,
    enable_ocr: bool = False,
    ocr_pages: list[int] | None = None,
    requirement_ids: set[str] | None = None,
) -> AnalysisRun:
    def ocr_runner(pdf_path: Path, pages: list[int]):
        return run_ocr_for_pages(
            pdf_path,
            pages,
            report_id=report.report_id,
            derived_dir=settings.derived_dir,
            ocrmypdf_cmd=settings.ocrmypdf_cmd,
            tesseract_cmd=settings.tesseract_cmd,
            ocr_lang=settings.ocr_lang,
        )

    profile_path = (
        ENVISION_2024_PROFILE_PATH
        if ENVISION_2024_PROFILE_PATH.exists() and Path(report.original_filename).name == "Envision Energy 2024-zh.pdf"
        else None
    )
    llm_client = LLMClient(
        model=settings.llm_model,
        api_key=settings.openai_compatible_api_key,
        base_url=settings.openai_compatible_api_base,
        thinking_type=settings.llm_thinking_type,
        reasoning_effort=settings.llm_reasoning_effort,
        response_format=settings.llm_response_format,
        max_tokens=settings.llm_max_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        retry_delay_seconds=settings.llm_retry_delay_seconds,
    )
    ai_assessment_service = AIAssessmentService(
        llm_client,
        prompt_version=settings.llm_prompt_version,
        max_concurrency=settings.llm_max_concurrency,
        max_calls_per_run=settings.llm_max_calls_per_run,
    )
    workflow = SingleReportWorkflow(
        repo,
        DocumentParser(ocr_runner=ocr_runner),
        GRIAdapter(GRI_REQUIREMENTS_PATH, max_requirements=GRI_REQUIREMENTS_LIMIT),
        DisclosureAgent(),
        requirement_pack_path=GRI_REQUIREMENT_PACK_PATH,
        report_profile_path=profile_path,
        ocr_max_pages=settings.ocr_max_pages,
        ai_assessment_service=ai_assessment_service,
    )
    result = workflow.run(
        report.report_id,
        Path(report.stored_path),
        report.file_hash,
        confirm_llm=confirm_llm,
        enable_ocr=enable_ocr,
        ocr_pages=ocr_pages,
        run_id=run_id,
        requirement_ids=requirement_ids,
    )
    if result.status is RunStatus.COMPLETED:
        report_status = ReportStatus.ANALYSIS_COMPLETED
    elif result.status is RunStatus.PARTIALLY_COMPLETED:
        report_status = ReportStatus.PARTIALLY_COMPLETED
    else:
        report_status = ReportStatus.ANALYSIS_FAILED
    repo.update_report_status(report.report_id, report_status)
    return result
