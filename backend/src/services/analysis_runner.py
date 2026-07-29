from pathlib import Path

from src.agents.disclosure_agent import DisclosureAgent
from src.config.settings import Settings
from src.db.repositories import Repository
from src.domain.enums import ReportStatus, RunStatus
from src.domain.models import AnalysisRun, Report
from src.reports.profile import load_report_profile
from src.reports.profile_resolver import ReportProfileResolver
from src.services.document_parser import DocumentParser
from src.services.ai_assessment_service import AIAssessmentService
from src.services.effective_run_view_service import EffectiveRunViewService
from src.services.ocr import run_ocr_for_pages
from src.standards.gri import GRIAdapter
from src.workflows.single_report_workflow import SingleReportWorkflow
from src.tools.llm_client import LLMClient


DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
GRI_REQUIREMENTS_PATH = DATA_ROOT / "manifests" / "gri_requirement_checklist_v3.json"
GRI_REQUIREMENT_PACK_PATH = DATA_ROOT / "manifests" / "gri_requirement_pack.json"
REPORT_PROFILE_ROOT = DATA_ROOT / "reports" / "profiles"
GRI_REQUIREMENTS_LIMIT = None


def resolve_effective_report_status(
    repo: Repository,
    *,
    report_id: str,
    run_result: AnalysisRun,
    independent_requirement_ids: set[str] | None = None,
) -> ReportStatus:
    if independent_requirement_ids is None:
        independent_requirement_ids = {
            requirement.requirement_id
            for requirement in GRIAdapter(GRI_REQUIREMENTS_PATH).load_requirements()
        }
    service = EffectiveRunViewService(repo)
    latest_run = repo.latest_run_for_report(report_id)
    if (
        latest_run is not None
        and service.lineage_contains_eligible_count(
            latest_run=latest_run,
            eligible_count=499,
        )
    ):
        view = service.build(
            report_id=report_id,
            independent_requirement_ids=independent_requirement_ids,
        )
        if not (
            view.failed_requirement_ids
            or view.not_generated_requirement_ids
        ):
            return ReportStatus.ANALYSIS_COMPLETED
        if view.assessments_by_requirement:
            return ReportStatus.PARTIALLY_COMPLETED
        return ReportStatus.ANALYSIS_FAILED
    if run_result.status is RunStatus.COMPLETED:
        return ReportStatus.ANALYSIS_COMPLETED
    if run_result.status is RunStatus.PARTIALLY_COMPLETED:
        return ReportStatus.PARTIALLY_COMPLETED
    return ReportStatus.ANALYSIS_FAILED


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

    if report.page_count is None:
        raise ValueError("report page count is required before analysis")
    profile_path = ReportProfileResolver(REPORT_PROFILE_ROOT).resolve(
        original_filename=report.original_filename,
        page_count=report.page_count,
        source_file_hash=report.file_hash,
    )
    profile_id = (
        load_report_profile(profile_path).report_id
        if profile_path is not None
        else None
    )
    repo.create_audit_event(
        run_id,
        "report_profile_resolved",
        {
            "report_id": report.report_id,
            "matched": profile_path is not None,
            "profile_id": profile_id,
        },
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
    report_status = resolve_effective_report_status(
        repo,
        report_id=report.report_id,
        run_result=result,
    )
    repo.update_report_status(report.report_id, report_status)
    return result
