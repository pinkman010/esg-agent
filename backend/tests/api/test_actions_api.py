import pytest

from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, Report

pytestmark = pytest.mark.anyio


def seed_action_source(session):
    repo = Repository(session)
    repo.create_report(Report(report_id="report-1", original_filename="report.pdf", stored_path="x", file_hash="hash-1"))
    repo.create_run(AnalysisRun(run_id="run-1", report_id="report-1", status=RunStatus.COMPLETED))
    repo.save_assessment(DisclosureAssessment(assessment_id="assessment-1", run_id="run-1", report_id="report-1", standard_id="GRI", standard_version="2021", disclosure_id="GRI 2-1", requirement_id="GRI 2-1-a", verdict=AssessmentVerdict.UNKNOWN, rationale="No evidence", review_status=ReviewStatus.NEEDS_MANUAL_REVIEW))


async def test_actions_api_creates_lists_and_completes_action_without_changing_assessment(api_client, api_session):
    seed_action_source(api_session)
    created = await api_client.post("/api/reports/report-1/actions", json={"assessment_id": "assessment-1", "title": "补充法定名称证据", "priority": "high", "owner_name": "张三", "recommendation_text": "在报告中补充披露", "created_by": "张三"})
    listed = await api_client.get("/api/reports/report-1/actions")
    completed_without_note = await api_client.patch(f"/api/actions/{created.json()['action_id']}", json={"status": "completed"})
    completed = await api_client.patch(f"/api/actions/{created.json()['action_id']}", json={"status": "completed", "completion_note": "已补充"})

    assert created.status_code == 200
    assert listed.json()[0]["assessment_id"] == "assessment-1"
    assert completed_without_note.status_code == 422
    assert completed.json()["status"] == "completed"
    assert Repository(api_session).get_assessment("assessment-1").verdict is AssessmentVerdict.UNKNOWN
