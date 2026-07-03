import pytest

pytestmark = pytest.mark.anyio

from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, EvidenceItem, Recommendation, Report


def seed_run(session):
    repo = Repository(session)
    repo.create_report(Report(report_id="report-1", original_filename="report.pdf", stored_path="x", file_hash="hash-1"))
    repo.create_run(AnalysisRun(run_id="run-1", report_id="report-1", status=RunStatus.COMPLETED))
    assessment = DisclosureAssessment(
        assessment_id="assessment-1",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 302",
        requirement_id="GRI 302-1-a",
        verdict=AssessmentVerdict.DISCLOSED,
        rationale="Evidence found.",
        evidence=[EvidenceItem(evidence_id="evidence-1", run_id="run-1", report_id="report-1", source_text="Energy", source_page=1, source_file_hash="hash-1", source_method=EvidenceSourceMethod.PDFPLUMBER)],
        review_status=ReviewStatus.NOT_REQUIRED,
    )
    repo.save_assessment(assessment)
    repo.save_evidence_item("assessment-1", assessment.evidence[0])
    repo.save_recommendation(Recommendation(recommendation_id="recommendation-1", run_id="run-1", report_id="report-1", disclosure_id="GRI 302", requirement_id="GRI 302-1-a", recommendation_text="Improve disclosure."))


async def test_runs_api_lists_run_detail_assessments_and_recommendations(api_client, api_session):
    seed_run(api_session)

    runs = await api_client.get("/api/runs")
    detail = await api_client.get("/api/runs/run-1")
    assessments = await api_client.get("/api/runs/run-1/assessments")
    recommendations = await api_client.get("/api/runs/run-1/recommendations")

    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == "run-1"
    assert detail.json()["status"] == "completed"
    assert assessments.json()[0]["evidence"][0]["source_page"] == 1
    assert recommendations.json()[0]["recommendation_id"] == "recommendation-1"