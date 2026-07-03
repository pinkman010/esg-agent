import pytest

pytestmark = pytest.mark.anyio

from src.db.repositories import Repository
from src.domain.enums import RunStatus
from src.domain.models import AnalysisRun, Report


def seed_audit_data(session):
    repo = Repository(session)
    repo.create_report(Report(report_id="report-1", original_filename="report.pdf", stored_path="x", file_hash="hash-1"))
    repo.create_audit_event(None, "report_uploaded", {"report_id": "report-1", "file_hash": "hash-1"})
    repo.create_run(
        AnalysisRun(
            run_id="run-1",
            report_id="report-1",
            status=RunStatus.FAILED,
            confirm_llm=True,
            error_message="Parse failed.",
        )
    )
    repo.create_audit_event("run-1", "workflow_failed", {"reason": "parse"})


async def test_audit_api_lists_run_events_with_report_context(api_client, api_session):
    seed_audit_data(api_session)

    response = await api_client.get("/api/audit/runs")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["run_id"] == "run-1"
    assert body[0]["report_id"] == "report-1"
    assert body[0]["file_hash"] == "hash-1"
    assert body[0]["model_called"] is True
    assert body[0]["error_message"] == "Parse failed."
    assert [event["event_type"] for event in body[0]["events"]] == ["report_uploaded", "workflow_failed"]
    assert body[0]["events"][0]["payload"] == {"report_id": "report-1", "file_hash": "hash-1"}
    assert body[0]["events"][1]["payload"] == {"reason": "parse"}
