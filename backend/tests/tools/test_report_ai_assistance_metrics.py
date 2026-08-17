import json
from types import SimpleNamespace

from src.tools.report_ai_assistance_metrics import (
    begin_read_only_transaction,
    build_suggestion_rows,
    generate_ai_assistance_report,
    summarize_ai_suggestions,
    write_report_files,
)


def suggestion(
    *,
    suggestion_id: str,
    assessment_id: str = "assessment-1",
    status: str,
    confidence: float | None = None,
    guardrail_codes: list[str] | None = None,
    error_code: str | None = None,
) -> dict[str, object]:
    return {
        "suggestion_id": suggestion_id,
        "assessment_id": assessment_id,
        "status": status,
        "suggested_verdict": "unknown" if status != "skipped" else None,
        "confidence": confidence,
        "guardrail_codes": guardrail_codes or [],
        "error_code": error_code,
        "latency_ms": 10,
        "retry_count": 0,
        "raw_response": {"private": "content"},
        "input_hash": "private-hash",
        "usage": {"total_tokens": 42},
    }


def snapshot(
    *,
    suggestion_id: str,
    reason_code: str,
    assessment_id: str = "assessment-1",
    created_at: str = "2026-08-17T10:00:00Z",
) -> dict[str, object]:
    return {
        "assessment_id": assessment_id,
        "reason_code": reason_code,
        "reviewer_note": f"人工处置；AI suggestion_id={suggestion_id}",
        "created_at": created_at,
    }


def test_metrics_separate_calls_skips_guardrails_failures_and_confidence_buckets():
    summary = summarize_ai_suggestions(
        run_id="run-1",
        confirm_llm=True,
        suggestions=[
            suggestion(
                suggestion_id="success-zero",
                status="succeeded",
                confidence=0.0,
            ),
            suggestion(
                suggestion_id="success-high",
                status="succeeded",
                confidence=0.82,
            ),
            suggestion(
                suggestion_id="guardrail",
                status="failed",
                confidence=0.2,
                guardrail_codes=["verdict_upgrade_requires_human_review"],
                error_code="ai_response_guardrail_failed",
            ),
            suggestion(
                suggestion_id="technical",
                status="failed",
                guardrail_codes=["llm_connection_error"],
                error_code="llm_connection_error",
            ),
            suggestion(
                suggestion_id="skipped-evidence",
                status="skipped",
                guardrail_codes=["no_substantive_evidence"],
                error_code="no_substantive_evidence",
            ),
            suggestion(
                suggestion_id="skipped-priority",
                status="skipped",
                guardrail_codes=["low_review_priority"],
                error_code="low_review_priority",
            ),
        ],
        snapshots=[],
    )

    assert summary["run_id"] == "run-1"
    assert summary["confirm_llm"] is True
    assert summary["suggestion_count"] == 6
    assert summary["called_count"] == 4
    assert summary["succeeded_count"] == 2
    assert summary["guardrail_blocked_count"] == 1
    assert summary["technical_failed_count"] == 1
    assert summary["skipped_count"] == 2
    assert summary["skip_reason_counts"] == {
        "low_review_priority": 1,
        "no_substantive_evidence": 1,
    }
    assert summary["confidence_bucket_counts"] == {
        "not_provided": 1,
        "0-19%": 1,
        "20-39%": 1,
        "40-59%": 0,
        "60-79%": 0,
        "80-100%": 1,
    }


def test_human_rates_only_use_latest_valid_resolution_for_matching_assessment():
    suggestions = [
        suggestion(suggestion_id="accepted", status="succeeded"),
        suggestion(suggestion_id="modified", status="succeeded"),
        suggestion(suggestion_id="rejected", status="succeeded"),
        suggestion(suggestion_id="unresolved", status="succeeded"),
    ]
    summary = summarize_ai_suggestions(
        run_id="run-1",
        confirm_llm=True,
        suggestions=suggestions,
        snapshots=[
            snapshot(
                suggestion_id="accepted",
                reason_code="ai_suggestion_rejected",
                created_at="2026-08-17T09:00:00Z",
            ),
            snapshot(
                suggestion_id="accepted",
                reason_code="ai_suggestion_accepted",
                created_at="2026-08-17T10:00:00Z",
            ),
            snapshot(
                suggestion_id="modified",
                reason_code="ai_suggestion_modified",
            ),
            snapshot(
                suggestion_id="rejected",
                reason_code="ai_suggestion_rejected",
            ),
            snapshot(
                suggestion_id="unresolved",
                reason_code="ai_suggestion_accepted",
                assessment_id="assessment-other",
            ),
        ],
    )

    assert summary["accepted_count"] == 1
    assert summary["modified_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["resolved_ai_suggestion_count"] == 3
    assert summary["acceptance_rate"] == 1 / 3
    assert summary["modification_rate"] == 1 / 3
    assert summary["rejection_rate"] == 1 / 3


def test_empty_human_resolution_rates_are_null():
    summary = summarize_ai_suggestions(
        run_id="run-1",
        confirm_llm=False,
        suggestions=[],
        snapshots=[],
    )

    assert summary["resolved_ai_suggestion_count"] == 0
    assert summary["acceptance_rate"] is None
    assert summary["modification_rate"] is None
    assert summary["rejection_rate"] is None


def test_suggestion_rows_only_contain_the_allowlisted_fields():
    rows = build_suggestion_rows(
        [suggestion(suggestion_id="success", status="succeeded", confidence=0.8)]
    )
    serialized = json.dumps(rows)

    assert set(rows[0]) == {
        "assessment_id",
        "status",
        "suggested_verdict",
        "confidence",
        "guardrail_codes",
        "error_code",
        "latency_ms",
        "retry_count",
    }
    assert "raw_response" not in serialized
    assert "input_hash" not in serialized
    assert "usage" not in serialized
    assert "api_key" not in serialized.lower()
    assert "database_url" not in serialized.lower()


def test_read_only_transaction_is_the_first_database_statement():
    class RecordingSession:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement):
            self.statements.append(str(statement))

    session = RecordingSession()

    begin_read_only_transaction(session)

    assert session.statements
    assert "READ ONLY" in session.statements[0].upper()


def test_report_files_use_safe_prefix_and_do_not_serialize_private_fields(tmp_path):
    suggestions = [
        suggestion(suggestion_id="success", status="succeeded", confidence=0.8)
    ]
    summary = summarize_ai_suggestions(
        run_id="run-1",
        confirm_llm=True,
        suggestions=suggestions,
        snapshots=[],
    )

    summary_path, rows_path = write_report_files(
        output_dir=tmp_path,
        output_prefix="envision_ai_routing",
        summary=summary,
        suggestion_rows=build_suggestion_rows(suggestions),
    )

    assert summary_path.name == "envision_ai_routing_summary.json"
    assert rows_path.name == "envision_ai_routing_suggestions.csv"
    serialized = summary_path.read_text(encoding="utf-8") + rows_path.read_text(
        encoding="utf-8"
    )
    assert "raw_response" not in serialized
    assert "private-hash" not in serialized
    assert "private" not in serialized


def test_generate_report_starts_read_only_and_reads_without_mutating_repository(
    tmp_path,
):
    class RecordingSession:
        def __init__(self):
            self.statements: list[str] = []

        def execute(self, statement):
            self.statements.append(str(statement))

    class ReadOnlyRepository:
        def __init__(self):
            self.calls: list[tuple[str, str]] = []

        def get_run(self, run_id):
            self.calls.append(("get_run", run_id))
            return SimpleNamespace(run_id=run_id, confirm_llm=True)

        def list_ai_suggestions_for_run(self, run_id):
            self.calls.append(("list_ai_suggestions_for_run", run_id))
            return [suggestion(suggestion_id="success", status="succeeded")]

        def list_review_snapshots(self, assessment_id):
            self.calls.append(("list_review_snapshots", assessment_id))
            return []

    session = RecordingSession()
    repository = ReadOnlyRepository()

    summary_path, rows_path = generate_ai_assistance_report(
        session=session,
        repository=repository,
        run_id="run-1",
        output_dir=tmp_path,
        output_prefix="run_1",
    )

    assert "READ ONLY" in session.statements[0].upper()
    assert repository.calls == [
        ("get_run", "run-1"),
        ("list_ai_suggestions_for_run", "run-1"),
        ("list_review_snapshots", "assessment-1"),
    ]
    assert summary_path.exists()
    assert rows_path.exists()
