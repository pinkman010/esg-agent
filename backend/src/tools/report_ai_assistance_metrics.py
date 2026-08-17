import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy import text


REVIEW_GUARDRAILS = frozenset(
    {
        "evidence_page_cardinality_mismatch",
        "duplicate_evidence_reference",
        "evidence_reference_out_of_scope",
        "evidence_page_mismatch",
        "disclosed_without_substantive_evidence",
        "verdict_upgrade_requires_human_review",
        "partial_without_missing_items",
    }
)
AI_REVIEW_REASON_CODES = frozenset(
    {
        "ai_suggestion_accepted",
        "ai_suggestion_modified",
        "ai_suggestion_rejected",
    }
)
SUGGESTION_ID_PATTERN = re.compile(
    r"(?:^|[；;]\s*)AI suggestion_id=([A-Za-z0-9-]+)(?:$|[；;])"
)
CONFIDENCE_BUCKETS = (
    "not_provided",
    "0-19%",
    "20-39%",
    "40-59%",
    "60-79%",
    "80-100%",
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "ai"
OUTPUT_PREFIX_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
SUGGESTION_ROW_FIELDS = (
    "assessment_id",
    "status",
    "suggested_verdict",
    "confidence",
    "guardrail_codes",
    "error_code",
    "latency_ms",
    "retry_count",
)


def begin_read_only_transaction(session: Any) -> None:
    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))


def build_suggestion_rows(
    suggestions: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {field: suggestion.get(field) for field in SUGGESTION_ROW_FIELDS}
        for suggestion in suggestions
    ]


def write_report_files(
    *,
    output_dir: Path,
    output_prefix: str,
    summary: dict[str, object],
    suggestion_rows: list[dict[str, object]],
) -> tuple[Path, Path]:
    if OUTPUT_PREFIX_PATTERN.fullmatch(output_prefix) is None:
        raise ValueError("output_prefix must contain only letters, numbers, dot, dash, or underscore")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"{output_prefix}_summary.json"
    rows_path = output_dir / f"{output_prefix}_suggestions.csv"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fieldnames = list(SUGGESTION_ROW_FIELDS)
    with rows_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in suggestion_rows:
            serialized = dict(row)
            guardrail_codes = serialized.get("guardrail_codes")
            if isinstance(guardrail_codes, list):
                serialized["guardrail_codes"] = ";".join(
                    str(code) for code in guardrail_codes
                )
            writer.writerow(serialized)
    return summary_path, rows_path


def generate_ai_assistance_report(
    *,
    session: Any,
    repository: Any,
    run_id: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    output_prefix: str,
) -> tuple[Path, Path]:
    begin_read_only_transaction(session)
    run = repository.get_run(run_id)
    if run is None:
        raise ValueError(f"analysis run not found: {run_id}")
    suggestion_dicts = [
        _model_to_dict(item)
        for item in repository.list_ai_suggestions_for_run(run_id)
    ]
    snapshots: list[dict[str, object]] = []
    assessment_ids = sorted(
        {
            str(item.get("assessment_id") or "")
            for item in suggestion_dicts
            if item.get("assessment_id")
        }
    )
    for assessment_id in assessment_ids:
        snapshots.extend(
            _model_to_dict(item)
            for item in repository.list_review_snapshots(assessment_id)
        )
    summary = summarize_ai_suggestions(
        run_id=run_id,
        confirm_llm=bool(run.confirm_llm),
        suggestions=suggestion_dicts,
        snapshots=snapshots,
    )
    return write_report_files(
        output_dir=output_dir,
        output_prefix=output_prefix,
        summary=summary,
        suggestion_rows=build_suggestion_rows(suggestion_dicts),
    )


def summarize_ai_suggestions(
    *,
    run_id: str,
    confirm_llm: bool,
    suggestions: list[dict[str, object]],
    snapshots: list[dict[str, object]],
) -> dict[str, object]:
    guardrail_code_counts: Counter[str] = Counter()
    error_code_counts: Counter[str] = Counter()
    skip_reason_counts: Counter[str] = Counter()
    confidence_bucket_counts: Counter[str] = Counter(
        {bucket: 0 for bucket in CONFIDENCE_BUCKETS}
    )
    succeeded_count = 0
    guardrail_blocked_count = 0
    technical_failed_count = 0
    skipped_count = 0

    for suggestion in suggestions:
        status = str(suggestion.get("status") or "")
        guardrail_codes = _string_list(suggestion.get("guardrail_codes"))
        error_code = str(suggestion.get("error_code") or "")
        guardrail_code_counts.update(guardrail_codes)
        if error_code:
            error_code_counts.update([error_code])

        if status == "succeeded":
            succeeded_count += 1
            confidence_bucket_counts.update(
                [_confidence_bucket(suggestion.get("confidence"))]
            )
        elif status == "failed":
            confidence_bucket_counts.update(
                [_confidence_bucket(suggestion.get("confidence"))]
            )
            if REVIEW_GUARDRAILS.intersection(guardrail_codes):
                guardrail_blocked_count += 1
            else:
                technical_failed_count += 1
        elif status == "skipped":
            skipped_count += 1
            skip_reason = error_code or next(iter(guardrail_codes), "unknown")
            skip_reason_counts.update([skip_reason])

    human_counts = _human_resolution_counts(suggestions, snapshots)
    resolved_count = sum(human_counts.values())

    def rate(count: int) -> float | None:
        return count / resolved_count if resolved_count else None

    accepted_count = human_counts["ai_suggestion_accepted"]
    modified_count = human_counts["ai_suggestion_modified"]
    rejected_count = human_counts["ai_suggestion_rejected"]
    return {
        "run_id": run_id,
        "confirm_llm": confirm_llm,
        "suggestion_count": len(suggestions),
        "called_count": succeeded_count
        + guardrail_blocked_count
        + technical_failed_count,
        "succeeded_count": succeeded_count,
        "guardrail_blocked_count": guardrail_blocked_count,
        "technical_failed_count": technical_failed_count,
        "skipped_count": skipped_count,
        "skip_reason_counts": dict(sorted(skip_reason_counts.items())),
        "guardrail_code_counts": dict(sorted(guardrail_code_counts.items())),
        "error_code_counts": dict(sorted(error_code_counts.items())),
        "confidence_bucket_counts": dict(confidence_bucket_counts),
        "accepted_count": accepted_count,
        "modified_count": modified_count,
        "rejected_count": rejected_count,
        "resolved_ai_suggestion_count": resolved_count,
        "acceptance_rate": rate(accepted_count),
        "modification_rate": rate(modified_count),
        "rejection_rate": rate(rejected_count),
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _confidence_bucket(value: object) -> str:
    if value is None:
        return "not_provided"
    confidence = float(value)
    if confidence < 0.2:
        return "0-19%"
    if confidence < 0.4:
        return "20-39%"
    if confidence < 0.6:
        return "40-59%"
    if confidence < 0.8:
        return "60-79%"
    return "80-100%"


def _human_resolution_counts(
    suggestions: list[dict[str, object]],
    snapshots: list[dict[str, object]],
) -> Counter[str]:
    suggestions_by_id = {
        str(suggestion.get("suggestion_id")): suggestion
        for suggestion in suggestions
        if suggestion.get("suggestion_id")
    }
    resolved_by_suggestion: dict[str, str] = {}
    for snapshot in sorted(
        snapshots,
        key=lambda item: str(item.get("created_at") or ""),
    ):
        reason_code = str(snapshot.get("reason_code") or "")
        if reason_code not in AI_REVIEW_REASON_CODES:
            continue
        match = SUGGESTION_ID_PATTERN.search(str(snapshot.get("reviewer_note") or ""))
        if match is None:
            continue
        suggestion_id = match.group(1)
        suggestion = suggestions_by_id.get(suggestion_id)
        if suggestion is None:
            continue
        if str(suggestion.get("assessment_id") or "") != str(
            snapshot.get("assessment_id") or ""
        ):
            continue
        resolved_by_suggestion[suggestion_id] = reason_code
    return Counter(resolved_by_suggestion.values())


def _model_to_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if not callable(model_dump):
        raise TypeError("report input must be a mapping or Pydantic model")
    return dict(model_dump(mode="json"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate read-only AI assistance metrics for one analysis run."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-prefix", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from src.db.repositories import Repository
    from src.db.session import SessionLocal

    args = parse_args(argv)
    with SessionLocal() as session:
        summary_path, rows_path = generate_ai_assistance_report(
            session=session,
            repository=Repository(session),
            run_id=args.run_id,
            output_prefix=args.output_prefix,
        )
        session.rollback()
    print(summary_path.relative_to(PROJECT_ROOT))
    print(rows_path.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
