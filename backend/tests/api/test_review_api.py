import pytest

pytestmark = pytest.mark.anyio

from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, EvidenceItem, Report


def seed_review_item(session):
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
        rationale="OCR evidence.",
        evidence=[EvidenceItem(evidence_id="evidence-1", run_id="run-1", report_id="report-1", source_text="Energy", source_page=1, source_file_hash="hash-1", source_method=EvidenceSourceMethod.OCR, is_kpi_evidence=True)],
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
    )
    repo.save_assessment(assessment)
    repo.save_evidence_item("assessment-1", assessment.evidence[0])


async def test_review_api_lists_and_saves_decision(api_client, api_session):
    seed_review_item(api_session)

    runs = await api_client.get("/api/review/runs")
    assessments = await api_client.get("/api/review/runs/run-1/assessments")
    decision = await api_client.post(
        "/api/review/runs/run-1/decisions",
        json={"assessment_id": "assessment-1", "review_status": "approved", "reviewer_note": "Checked."},
    )

    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == "run-1"
    assert assessments.json()[0]["review_status"] == "needs_manual_review"
    assert decision.status_code == 200
    assert decision.json()["review_status"] == "approved"
    assert Repository(api_session).count_audit_events("run-1") == 1


async def test_new_review_api_appends_snapshot_and_returns_history(api_client, api_session):
    seed_review_item(api_session)

    response = await api_client.post(
        "/api/assessments/assessment-1/review-decisions",
        json={
            "operation_type": "modify",
            "reviewer_name": "张三",
            "reason_code": "evidence_scope_corrected",
            "reviewer_note": "修正证据范围",
            "reviewed_verdict": "partially_disclosed",
            "evidence_pages": [1],
            "rationale": "人工判断依据",
            "missing_items": ["缺少计算方法"],
        },
    )
    history = await api_client.get("/api/assessments/assessment-1/review-history")

    assert response.status_code == 200
    assert response.json()["sequence"] == 1
    assert response.json()["reviewer_name"] == "张三"
    assert history.status_code == 200
    assert history.json()[0]["reviewed_verdict"] == "partially_disclosed"


async def test_new_review_api_returns_409_for_stale_snapshot(api_client, api_session):
    seed_review_item(api_session)
    await api_client.post(
        "/api/assessments/assessment-1/review-decisions",
        json={"operation_type": "approve", "reviewer_name": "张三", "reason_code": "system_result_confirmed"},
    )

    response = await api_client.post(
        "/api/assessments/assessment-1/review-decisions",
        json={
            "operation_type": "approve",
            "reviewer_name": "李四",
            "reason_code": "system_result_confirmed",
            "expected_previous_snapshot_id": "stale",
        },
    )

    assert response.status_code == 409
