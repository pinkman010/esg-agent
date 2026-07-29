import pytest

from src.db.repositories import Repository
from src.domain.enums import RunStatus
from src.domain.models import AnalysisRun, Report

pytestmark = pytest.mark.anyio


def seed_report_audit_data(session):
    repo = Repository(session)
    for report_id in ("report-audit-1", "report-audit-2"):
        repo.create_report(
            Report(
                report_id=report_id,
                original_filename=f"{report_id}.pdf",
                stored_path="x",
                file_hash=f"hash-{report_id}",
            )
        )
        repo.create_audit_event(
            None,
            "report_uploaded",
            {
                "report_id": report_id,
                "file_hash": f"hash-{report_id}",
            },
        )
    repo.create_run(
        AnalysisRun(
            run_id="run-audit-1",
            report_id="report-audit-1",
            status=RunStatus.COMPLETED,
        )
    )
    repo.create_run(
        AnalysisRun(
            run_id="run-audit-2",
            report_id="report-audit-1",
            status=RunStatus.FAILED,
        )
    )
    repo.create_run(
        AnalysisRun(
            run_id="run-other",
            report_id="report-audit-2",
            status=RunStatus.COMPLETED,
        )
    )
    repo.create_audit_event(
        "run-audit-1",
        "analysis_completed",
        {"report_id": "report-audit-1", "assessment_count": 499},
    )
    repo.create_audit_event(
        "run-audit-2",
        "analysis_failed",
        {
            "report_id": "report-audit-1",
            "error_code": "analysis_execution_failed",
            "error": (
                "failed at C:\\private\\report.pdf "
                "Authorization: Bearer secret-token"
            ),
            "stored_path": "C:\\private\\report.pdf",
            "nested": {
                "api_key": "private-key",
                "failed_requirement_ids": ["GRI 2-1-a"],
            },
        },
    )
    repo.create_audit_event(
        "run-other",
        "analysis_completed",
        {"report_id": "report-audit-2", "assessment_count": 499},
    )


async def test_report_audit_lists_all_report_events_with_safe_projection(
    api_client,
    api_session,
):
    seed_report_audit_data(api_session)

    response = await api_client.get(
        "/api/reports/report-audit-1/audit",
        params={"offset": 0, "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["offset"] == 0
    assert body["limit"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["event_type"] == "analysis_failed"
    assert body["items"][0]["run_id"] == "run-audit-2"
    assert body["items"][1]["event_type"] == "analysis_completed"
    serialized = str(body)
    assert "run-other" not in serialized
    assert "report-audit-2" not in serialized
    assert "C:\\private" not in serialized
    assert "secret-token" not in serialized
    assert "private-key" not in serialized
    failed_payload = body["items"][0]["payload"]
    assert "stored_path" not in failed_payload
    assert "api_key" not in failed_payload["nested"]
    assert failed_payload["nested"]["failed_requirement_ids"] == [
        "GRI 2-1-a"
    ]
    assert failed_payload["error_code"] == "analysis_execution_failed"


async def test_report_audit_supports_event_filter_and_offset(
    api_client,
    api_session,
):
    seed_report_audit_data(api_session)

    filtered = await api_client.get(
        "/api/reports/report-audit-1/audit",
        params={"event_type": "analysis_completed"},
    )
    offset = await api_client.get(
        "/api/reports/report-audit-1/audit",
        params={"offset": 2, "limit": 2},
    )

    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["run_id"] == "run-audit-1"
    assert offset.status_code == 200
    assert offset.json()["total"] == 3
    assert len(offset.json()["items"]) == 1
    assert offset.json()["items"][0]["event_type"] == "report_uploaded"
    assert offset.json()["items"][0]["run_id"] is None


async def test_report_audit_returns_404_and_validates_pagination(
    api_client,
):
    missing = await api_client.get("/api/reports/missing/audit")
    invalid_offset = await api_client.get(
        "/api/reports/missing/audit",
        params={"offset": -1},
    )
    invalid_limit = await api_client.get(
        "/api/reports/missing/audit",
        params={"limit": 101},
    )

    assert missing.status_code == 404
    assert invalid_offset.status_code == 422
    assert invalid_limit.status_code == 422
