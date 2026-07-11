import pytest

pytestmark = pytest.mark.anyio

from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, AnalysisStageEvent, DisclosureAssessment, EvidenceItem, Recommendation, Report


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


async def test_runs_api_returns_latest_stage_events(api_client, api_session):
    seed_run(api_session)
    repo = Repository(api_session)
    repo.append_analysis_stage_event(
        AnalysisStageEvent(run_id="run-1", stage_code="pdf_parsing", status="running", completed_units=0, total_units=1)
    )
    repo.append_analysis_stage_event(
        AnalysisStageEvent(run_id="run-1", stage_code="pdf_parsing", status="completed", completed_units=1, total_units=1)
    )

    response = await api_client.get("/api/runs/run-1/stages")

    assert response.status_code == 200
    assert response.json() == [
        {
            "stage_code": "pdf_parsing",
            "status": "completed",
            "completed_units": 1,
            "total_units": 1,
            "error_summary": None,
            "created_at": response.json()[0]["created_at"],
        }
    ]


async def test_retry_failed_creates_child_run_for_failed_requirements(api_client, api_session, monkeypatch):
    monkeypatch.setattr("src.api.routes.runs.execute_analysis", lambda *args, **kwargs: None)
    repo = Repository(api_session)
    repo.create_report(Report(report_id="report-1", original_filename="report.pdf", stored_path="x", file_hash="hash-1"))
    repo.create_run(
        AnalysisRun(
            run_id="run-1",
            report_id="report-1",
            status=RunStatus.PARTIALLY_COMPLETED,
            failed_requirement_count=1,
            failure_summary={"failed_requirement_ids": ["GRI 2-1-b"]},
        )
    )

    response = await api_client.post("/api/runs/run-1/retry-failed", json={"reason": "修复后重跑"})

    assert response.status_code == 200
    assert response.json()["parent_run_id"] == "run-1"
    assert response.json()["failure_summary"]["retry_requirement_ids"] == ["GRI 2-1-b"]
