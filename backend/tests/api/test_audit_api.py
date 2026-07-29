import pytest

from src.db.repositories import Repository
from src.domain.enums import RunStatus
from src.domain.models import AnalysisRun, Report

pytestmark = pytest.mark.anyio


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


async def test_legacy_audit_api_sanitizes_errors_and_event_payloads(
    api_client,
    api_session,
):
    repo = Repository(api_session)
    repo.create_report(
        Report(
            report_id="report-sensitive",
            original_filename="report.pdf",
            stored_path="x",
            file_hash="hash-sensitive",
        )
    )
    repo.create_run(
        AnalysisRun(
            run_id="run-sensitive",
            report_id="report-sensitive",
            status=RunStatus.FAILED,
            error_message=(
                r"failed C:\private\report.pdf and /home/alvin/report.pdf "
                "api_key=secret-value"
            ),
        )
    )
    repo.create_audit_event(
        "run-sensitive",
        "workflow_failed",
        {
            "stderr": "raw process output",
            "message": "see /tmp/esg/run.log Authorization: Bearer token-value",
        },
    )

    response = await api_client.get("/api/audit/runs")

    assert response.status_code == 200
    item = next(
        run for run in response.json() if run["run_id"] == "run-sensitive"
    )
    serialized = str(item)
    assert "C:\\private" not in serialized
    assert "/home/alvin" not in serialized
    assert "/tmp/esg" not in serialized
    assert "secret-value" not in serialized
    assert "token-value" not in serialized
    assert "raw process output" not in serialized
    assert "[path redacted]" in item["error_message"]
    assert "stderr" not in item["events"][0]["payload"]
