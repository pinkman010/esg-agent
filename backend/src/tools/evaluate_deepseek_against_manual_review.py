import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from src.config.settings import Settings, get_settings
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.domain.enums import AISuggestionStatus
from src.services.ai_assessment_service import (
    AIAssessmentCandidate,
    AIAssessmentService,
    build_ai_assessment_messages,
)
from src.services.ai_evaluation_service import (
    AIEvaluationCase,
    evaluate_ai_suggestions,
    load_adjudication_pending_ids,
    load_manual_review_baseline,
)
from src.standards.gri import GRIAdapter
from src.tools.llm_client import LLMClient


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_REQUIREMENTS = BACKEND_ROOT / "data/manifests/gri_requirement_checklist_v2.json"
DEFAULT_ASSETS_MANIFEST = BACKEND_ROOT / "data/manifests/assets_manifest.json"
DEFAULT_ADJUDICATION_RECOMMENDATIONS = (
    BACKEND_ROOT
    / "data/review_inputs/envision_2024/manual/envision_2024_577_Pro_second_review_recommendations_20260719.csv"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate DeepSeek suggestions against the fixed Envision manual review baseline."
    )
    parser.add_argument("--review-workbook", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, default=225)
    parser.add_argument("--expected-count", type=int, default=225)
    parser.add_argument(
        "--adjudication-recommendations",
        type=Path,
        default=DEFAULT_ADJUDICATION_RECOMMENDATIONS,
    )
    parser.add_argument("--retry-hard-gate-failures", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm-llm", action="store_true")
    return parser.parse_args(argv)


def build_evaluation_cases(
    repository: Repository,
    *,
    review_workbook: Path,
    requirements_path: Path,
    expected_count: int = 225,
) -> tuple[list[AIEvaluationCase], str, str]:
    baseline = load_manual_review_baseline(
        review_workbook,
        expected_count=expected_count,
    )
    report = repository.get_report(baseline.report_id)
    if report is None:
        raise ValueError(f"fixed report not found in database: {baseline.report_id}")
    run = repository.get_run(baseline.run_id)
    if run is None or run.report_id != baseline.report_id:
        raise ValueError(f"fixed analysis run not found in database: {baseline.run_id}")

    assessments = {
        assessment.requirement_id: assessment
        for assessment in repository.list_assessments_by_run(baseline.run_id)
    }
    tasks = {
        task.requirement_id: task
        for task in GRIAdapter(requirements_path).build_tasks(
            run_id=baseline.run_id,
            report_id=baseline.report_id,
        )
    }
    selected_assessment_ids = [
        assessments[record.requirement_id].assessment_id
        for record in baseline.records
        if record.requirement_id in assessments
    ]
    risks = repository.latest_risks_for_assessments(selected_assessment_ids)

    cases: list[AIEvaluationCase] = []
    for record in baseline.records:
        assessment = assessments.get(record.requirement_id)
        if assessment is None:
            raise ValueError(
                f"fixed run assessment not found: {record.requirement_id}"
            )
        task = tasks.get(record.requirement_id)
        if task is None:
            raise ValueError(
                f"v2 effective requirement not found: {record.requirement_id}"
            )
        risk = risks.get(assessment.assessment_id)
        if risk is None:
            raise ValueError(
                f"review priority not found for assessment: {assessment.assessment_id}"
            )
        cases.append(
            AIEvaluationCase(
                manual=record,
                candidate=AIAssessmentCandidate(
                    task=task,
                    assessment=assessment,
                    review_priority=risk.risk_level,
                ),
            )
        )
    return cases, baseline.report_id, baseline.run_id


def run_evaluation(
    args: argparse.Namespace,
    *,
    repository: Repository,
    settings: Settings,
) -> dict[str, Any]:
    cases, report_id, run_id = build_evaluation_cases(
        repository,
        review_workbook=args.review_workbook,
        requirements_path=args.requirements,
        expected_count=args.expected_count,
    )
    adjudication_pending_ids = load_adjudication_pending_ids(
        args.adjudication_recommendations
    )
    selected_ids = {case.manual.requirement_id for case in cases}
    adjudication_pending_ids &= selected_ids
    prompt_details = []
    for case in cases:
        messages, input_hash = build_ai_assessment_messages(case.candidate)
        prompt_details.append(
            {
                "requirement_id": case.manual.requirement_id,
                "input_hash": input_hash,
                "estimated_input_characters": sum(
                    len(message["content"]) for message in messages
                ),
                "evidence_count": min(
                    len(case.candidate.assessment.evidence),
                    5,
                ),
            }
        )

    if args.dry_run:
        rows = [
            {
                **detail,
                "manual_applicability": case.manual.manual_applicability,
                "manual_verdict": (
                    case.manual.suggested_verdict.value
                    if case.manual.suggested_verdict
                    else ""
                ),
                "is_applicability_exception": case.manual.is_applicability_exception,
                "is_adjudication_pending": (
                    case.manual.requirement_id in adjudication_pending_ids
                ),
                "rule_verdict": case.candidate.assessment.verdict.value,
                "review_priority": case.candidate.review_priority.value,
                "dry_run": True,
            }
            for case, detail in zip(cases, prompt_details, strict=True)
        ]
        summary = {
            "dry_run": True,
            "report_id": report_id,
            "run_id": run_id,
            "selected_count": len(cases),
            "verdict_evaluable_count": sum(
                case.manual.suggested_verdict is not None for case in cases
            ),
            "applicability_exception_count": sum(
                case.manual.is_applicability_exception for case in cases
            ),
            "adjudication_pending_count": len(adjudication_pending_ids),
            "estimated_call_count": min(len(cases), args.max_calls),
            "estimated_input_characters": sum(
                detail["estimated_input_characters"] for detail in prompt_details
            ),
            "configuration": settings.llm_configuration_summary(),
        }
        _write_outputs(args.output_csv, args.output_summary, rows, summary)
        return summary

    if not settings.openai_compatible_api_key.strip():
        raise ValueError("OPENAI_COMPATIBLE_API_KEY is not configured")
    client = LLMClient(
        model=settings.llm_model,
        api_key=settings.openai_compatible_api_key,
        base_url=settings.openai_compatible_api_base,
        thinking_type=settings.llm_thinking_type,
        reasoning_effort=settings.llm_reasoning_effort,
        response_format=settings.llm_response_format,
        max_tokens=settings.llm_max_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        retry_delay_seconds=settings.llm_retry_delay_seconds,
    )
    service = AIAssessmentService(
        client,
        prompt_version=settings.llm_prompt_version,
        max_concurrency=settings.llm_max_concurrency,
        max_calls_per_run=args.max_calls,
    )
    retry_requirement_ids: set[str] = set()
    if args.retry_hard_gate_failures:
        existing_suggestions = [
            suggestion
            for case in cases
            if (
                suggestion := repository.get_latest_ai_suggestion(
                    case.candidate.assessment.assessment_id
                )
            )
        ]
        if len(existing_suggestions) != len(cases):
            raise ValueError(
                "targeted retry requires an existing suggestion for every evaluation case"
            )
        existing_result = evaluate_ai_suggestions(
            cases,
            existing_suggestions,
            adjudication_pending_ids=adjudication_pending_ids,
        )
        retry_requirement_ids = {
            row["requirement_id"]
            for row in existing_result.rows
            if row["unsupported_evidence_reference"]
            or row["schema_failure"]
            or row["model_failure"]
            or (
                not row["is_adjudication_pending"]
                and (row["false_disclosed"] or row["wrong_source_page"])
            )
        }
        call_cases = [
            case
            for case in cases
            if case.manual.requirement_id in retry_requirement_ids
        ]
    else:
        call_cases = cases

    suggestions = service.assess_explicit_candidates(
        [case.candidate for case in call_cases],
        confirm_llm=True,
    )
    attempted_ids: list[str] = []
    for suggestion in suggestions:
        repository.append_ai_suggestion(suggestion)
        if suggestion.status is not AISuggestionStatus.SKIPPED:
            attempted_ids.append(suggestion.assessment_id)
    repository.mark_assessments_model_called(attempted_ids)

    latest_suggestions = [
        suggestion
        for case in cases
        if (
            suggestion := repository.get_latest_ai_suggestion(
                case.candidate.assessment.assessment_id
            )
        )
    ]
    if len(latest_suggestions) != len(cases):
        raise ValueError("evaluation result is missing persisted AI suggestions")
    assessment_to_requirement = {
        case.candidate.assessment.assessment_id: case.manual.requirement_id
        for case in cases
    }
    suggestion_history_counts = Counter(
        suggestion.assessment_id
        for suggestion in repository.list_ai_suggestions_for_run(run_id)
        if suggestion.assessment_id in assessment_to_requirement
    )
    cumulative_retry_count = sum(
        max(count - 1, 0) for count in suggestion_history_counts.values()
    )
    cumulative_retry_requirement_ids = sorted(
        assessment_to_requirement[assessment_id]
        for assessment_id, count in suggestion_history_counts.items()
        if count > 1
    )
    result = evaluate_ai_suggestions(
        cases,
        latest_suggestions,
        adjudication_pending_ids=adjudication_pending_ids,
    )
    summary = {
        **result.summary,
        "dry_run": False,
        "report_id": report_id,
        "run_id": run_id,
        "model": settings.llm_model,
        "prompt_version": settings.llm_prompt_version,
        "prompt_versions": sorted(
            {suggestion.prompt_version for suggestion in latest_suggestions}
        ),
        "evaluation_retry_attempt_count": cumulative_retry_count,
        "evaluation_retry_requirement_ids": cumulative_retry_requirement_ids,
        "latest_invocation_call_count": len(call_cases),
        "executed_at": date.today().isoformat(),
    }
    _write_outputs(args.output_csv, args.output_summary, result.rows, summary)
    return summary


def assert_hard_gates(summary: dict[str, Any], *, expected_count: int = 225) -> None:
    expected = {
        "evaluated_count": expected_count,
        "unsupported_evidence_reference_count": 0,
        "wrong_source_page_count": 0,
        "schema_failure_count": 0,
        "false_disclosed_count": 0,
        "model_failure_count": 0,
    }
    failures = {
        key: {"expected": value, "actual": summary.get(key)}
        for key, value in expected.items()
        if summary.get(key) != value
    }
    if failures:
        raise ValueError(f"AI evaluation hard gate failed: {failures}")


def register_evaluation_assets(
    *,
    assets_manifest: Path,
    output_paths: list[Path],
    summary: dict[str, Any],
) -> None:
    raw = json.loads(assets_manifest.read_text(encoding="utf-8-sig"))
    target_paths = {
        path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): path
        for path in output_paths
    }
    raw["assets"] = [
        item
        for item in raw.get("assets", [])
        if item.get("target_path") not in target_paths
    ]
    for target_path, path in target_paths.items():
        content = path.read_bytes()
        raw["assets"].append(
            {
                "source_path": "generated by DeepSeek manual-baseline evaluation CLI",
                "target_path": target_path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "asset_type": "ai_manual_baseline_evaluation",
                "material_status": "derived_validation_data",
                "model": summary["model"],
                "prompt_version": summary["prompt_version"],
                "report_id": summary["report_id"],
                "run_id": summary["run_id"],
                "evaluated_at": summary["executed_at"],
                "source_protection": "manual review workbook and source report were not modified",
            }
        )
    assets_manifest.write_text(
        json.dumps(raw, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )


def _write_outputs(
    csv_path: Path,
    summary_path: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_rows = [
        {
            key: (
                json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (list, dict))
                else value
            )
            for key, value in row.items()
        }
        for row in rows
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(normalized_rows[0]) if normalized_rows else [])
        if normalized_rows:
            writer.writeheader()
            writer.writerows(normalized_rows)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    session = SessionLocal()
    try:
        summary = run_evaluation(
            args,
            repository=Repository(session),
            settings=settings,
        )
        if args.confirm_llm:
            assert_hard_gates(summary, expected_count=args.expected_count)
            register_evaluation_assets(
                assets_manifest=DEFAULT_ASSETS_MANIFEST,
                output_paths=[args.output_csv, args.output_summary],
                summary=summary,
            )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
