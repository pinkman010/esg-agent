import pytest

from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReportStatus, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, EvidenceItem, Report
from src.services.risk_service import calculate_and_store_risk
from src.services.review_service import ReviewService
from src.domain.enums import ReviewOperation

pytestmark = pytest.mark.anyio


def seed_assessments(session):
    repo = Repository(session)
    repo.create_report(
        Report(
            report_id="report-1",
            original_filename="report.pdf",
            stored_path="x",
            file_hash="hash-1",
            status=ReportStatus.ANALYSIS_COMPLETED,
        )
    )
    repo.create_run(AnalysisRun(run_id="run-1", report_id="report-1", status=RunStatus.COMPLETED))
    disclosed = DisclosureAssessment(
        assessment_id="assessment-low",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        verdict=AssessmentVerdict.DISCLOSED,
        rationale="Direct evidence.",
        evidence=[
            EvidenceItem(
                evidence_id="evidence-1",
                run_id="run-1",
                report_id="report-1",
                source_text="Legal name",
                source_page=1,
                source_file_hash="hash-1",
                source_method=EvidenceSourceMethod.PDFPLUMBER,
            )
        ],
        review_status=ReviewStatus.NOT_REQUIRED,
    )
    unknown = DisclosureAssessment(
        assessment_id="assessment-high",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-b",
        verdict=AssessmentVerdict.UNKNOWN,
        rationale="No evidence.",
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
    )
    for item in (disclosed, unknown):
        repo.save_assessment(item)
        for evidence in item.evidence:
            repo.save_evidence_item(item.assessment_id, evidence)
        calculate_and_store_risk(repo, item, trigger_event="analysis_completed")


async def test_dashboard_and_review_queue_use_latest_risk_records(api_client, api_session):
    seed_assessments(api_session)

    dashboard = await api_client.get("/api/reports/report-1/dashboard")
    queue = await api_client.get("/api/reports/report-1/review-queue")
    assessments = await api_client.get("/api/reports/report-1/assessments")

    assert dashboard.status_code == 200
    assert dashboard.json()["high_risk_total"] == 1
    assert dashboard.json()["high_risk_reviewed"] == 0
    assert queue.json()["total"] == 1
    assert queue.json()["items"][0]["requirement_id"] == "GRI 2-1-b"
    assert assessments.json()["total"] == 2
    assert {item["risk_level"] for item in assessments.json()["items"]} == {"high", "low"}

    ReviewService(Repository(api_session)).record(
        "assessment-high",
        operation_type=ReviewOperation.APPROVE,
        reviewer_name="张三",
        reason_code="system_result_confirmed",
    )
    reviewed_dashboard = await api_client.get("/api/reports/report-1/dashboard")
    reviewed_queue = await api_client.get("/api/reports/report-1/review-queue")
    assert reviewed_dashboard.json()["high_risk_reviewed"] == 1
    assert reviewed_queue.json()["total"] == 0


async def test_assessment_detail_exposes_business_evidence_without_internal_route_metadata(api_client, api_session):
    seed_assessments(api_session)

    response = await api_client.get("/api/reports/report-1/assessments/assessment-low")

    assert response.status_code == 200
    body = response.json()
    assert body["assessment_id"] == "assessment-low"
    assert body["evidence_items"][0]["source_pdf_page"] == 1
    assert "metadata" not in body["evidence_items"][0]
    assert "candidate_pdf_pages" not in str(body)
