from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from src.config.settings import PROJECT_ROOT, get_settings
from src.db.models import (
    AIAssessmentSuggestionRecord,
    AnalysisRunRecord,
    AnalysisStageEventRecord,
    AssessmentRecord,
    AssessmentRiskRecord,
    AuditEventRecord,
    DisclosureTaskRecord,
    DocumentChunkRecord,
    DocumentPageRecord,
    EvidenceItemRecord,
    ExportVersionRecord,
    ImprovementActionRecord,
    RecommendationRecord,
    ReportRecord,
    ReviewChangeEventRecord,
    ReviewDecisionRecord,
    ReviewSnapshotRecord,
    StandardRequirementRecord,
)
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.tools.build_shadow_rag_contexts import (
    load_shadow_contexts_from_cases,
    write_shadow_contexts,
)
from src.tools.shadow_context_acceptance import (
    audit_contexts,
    build_acceptance_summary,
    load_comparison_inputs,
    render_acceptance_report,
)
from src.tools.shadow_vector_retrieval import resolve_shadow_output


EXPECTED_CASE_COUNT = 499
EXPECTED_EVALUATED_CASE_COUNT = 119
IMPLEMENTATION_RELATIVE_PATHS = (
    "backend/src/tools/shadow_context_acceptance.py",
    "backend/src/tools/finalize_shadow_rag_phase1.py",
    "backend/src/tools/build_shadow_rag_contexts.py",
    "backend/src/tools/evaluate_shadow_retrieval.py",
)
RETRIEVAL_PARAMETERS = {
    "retrieval_mode": "hybrid_rrf",
    "vector_pool_k": 10,
    "context_k": 5,
    "rrf_rule_weight": 2.0,
    "rrf_vector_weight": 1.0,
    "rrf_constant": 60,
}
CASE_FIELDNAMES = [
    "report_id",
    "requirement_id",
    "gold_pages",
    "rule_pages",
    "vector_pages",
    "hybrid_pages",
    "rule_first_hit_rank",
    "vector_first_hit_rank",
    "hybrid_first_hit_rank",
    "rule_hit_at_1",
    "rule_hit_at_3",
    "rule_hit_at_5",
    "vector_hit_at_1",
    "vector_hit_at_3",
    "vector_hit_at_5",
    "hybrid_hit_at_1",
    "hybrid_hit_at_3",
    "hybrid_hit_at_5",
    "rule_recall_at_1",
    "rule_recall_at_3",
    "rule_recall_at_5",
    "vector_recall_at_1",
    "vector_recall_at_3",
    "vector_recall_at_5",
    "hybrid_recall_at_1",
    "hybrid_recall_at_3",
    "hybrid_recall_at_5",
    "comparison_bucket",
    "context_hash",
    "context_size",
    "duplicate_page_count",
    "unresolved_rule_pages",
]

DEFAULT_REQUIREMENTS = (
    PROJECT_ROOT / "backend/data/manifests/gri_requirement_checklist_v3.json"
)
DEFAULT_BASELINE = (
    PROJECT_ROOT / "backend/data/review_inputs/envision_2024/baselines/"
    "current_577_review_regenerated.csv"
)
DEFAULT_MANUAL_REVIEW = (
    PROJECT_ROOT / "backend/data/review_inputs/envision_2024/manual/"
    "envision_2024_577_manual_review_second_review_Pro_20260719.xlsx"
)
DEFAULT_FINAL_ADJUDICATIONS = (
    PROJECT_ROOT / "backend/data/review_inputs/envision_2024/adjudication/"
    "envision_2024_result_adjudication_v1.csv"
)
DEFAULT_REPORT_PDF = PROJECT_ROOT / "backend/data/reports/Envision Energy 2024-zh.pdf"


FORMAL_TABLE_MODELS = {
    "reports": ReportRecord,
    "analysis_runs": AnalysisRunRecord,
    "analysis_stage_events": AnalysisStageEventRecord,
    "document_pages": DocumentPageRecord,
    "document_chunks": DocumentChunkRecord,
    "standard_requirements": StandardRequirementRecord,
    "disclosure_tasks": DisclosureTaskRecord,
    "assessments": AssessmentRecord,
    "ai_assessment_suggestions": AIAssessmentSuggestionRecord,
    "assessment_risks": AssessmentRiskRecord,
    "evidence_items": EvidenceItemRecord,
    "recommendations": RecommendationRecord,
    "review_decisions": ReviewDecisionRecord,
    "review_snapshots": ReviewSnapshotRecord,
    "review_change_events": ReviewChangeEventRecord,
    "improvement_actions": ImprovementActionRecord,
    "export_versions": ExportVersionRecord,
    "audit_events": AuditEventRecord,
}


def ensure_offline_phase1_5(*, embedding_enabled: bool) -> None:
    if embedding_enabled:
        raise RuntimeError("Phase 1.5 finalization requires EMBEDDING_ENABLED=false")


def ensure_demo_phase1_5(*, app_env: str, database_url: str) -> None:
    database_name = make_url(database_url).database
    if app_env != "demo" or database_name != "esg_agent_demo":
        raise RuntimeError(
            "Phase 1.5 finalization requires APP_ENV=demo and database esg_agent_demo"
        )


def validate_git_head(*, supplied_head: str, actual_head: str) -> str:
    normalized_supplied = supplied_head.strip().lower()
    normalized_actual = actual_head.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", normalized_supplied):
        raise ValueError("git_head must be a full 40-character hexadecimal commit hash")
    if normalized_supplied != normalized_actual:
        raise ValueError(
            f"git_head mismatch: supplied {normalized_supplied}, actual {normalized_actual}"
        )
    return normalized_actual


def capture_git_state(*, project_root: Path, supplied_head: str) -> dict[str, Any]:
    head_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    actual_head = validate_git_head(
        supplied_head=supplied_head,
        actual_head=head_result.stdout,
    )
    status_result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    status = status_result.stdout.rstrip()
    changed_paths = [
        line[3:].strip()
        for line in status.splitlines()
        if len(line) >= 4 and line[3:].strip()
    ]
    return {
        "head": actual_head,
        "dirty": bool(status),
        "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
        "changed_paths": changed_paths,
    }


def capture_formal_table_counts(session) -> dict[str, int]:
    return {
        table_name: int(session.scalar(select(func.count()).select_from(model)) or 0)
        for table_name, model in FORMAL_TABLE_MODELS.items()
    }


def fingerprint_file(
    path: Path,
    *,
    project_root: Path,
) -> dict[str, str | int]:
    content = path.read_bytes()
    return {
        "path": path.resolve().relative_to(project_root.resolve()).as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }


def _context_hashes(
    contexts: list[dict[str, Any]],
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for context in contexts:
        requirement_id = str(context.get("requirement_id") or "").strip()
        if not requirement_id or requirement_id in hashes:
            raise ValueError("duplicate or empty requirement_id during hash check")
        hashes[requirement_id] = str(context.get("context_hash") or "")
    return hashes


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CASE_FIELDNAMES)
        writer.writeheader()
        for case in cases:
            row = {}
            for field_name in CASE_FIELDNAMES:
                value = case.get(field_name)
                if isinstance(value, (list, dict)):
                    row[field_name] = json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                elif value is None:
                    row[field_name] = ""
                else:
                    row[field_name] = value
            writer.writerow(row)


def _manifest_output_names(
    output_prefix: str,
) -> tuple[str, str]:
    parent = Path(output_prefix).parent
    return (
        (parent / "envision_phase1_5_input_manifest.json").as_posix(),
        (parent / "envision_phase1_5_formal_state.json").as_posix(),
    )


def finalize_phase1_5(
    *,
    report_id: str,
    retrieval_cases_path: Path,
    requirements_path: Path,
    baseline_path: Path,
    manual_review_path: Path,
    final_adjudications_path: Path,
    report_pdf_path: Path,
    context_output: str,
    output_prefix: str,
    report_total_pages: int,
    git_head: str,
) -> dict[str, Any]:
    settings = get_settings()
    ensure_offline_phase1_5(embedding_enabled=settings.embedding_enabled)
    ensure_demo_phase1_5(
        app_env=settings.app_env,
        database_url=settings.database_url,
    )
    git_state = capture_git_state(
        project_root=PROJECT_ROOT,
        supplied_head=git_head,
    )
    if report_total_pages != 78:
        raise ValueError("Phase 1.5 requires report_total_pages=78")
    if not report_id.strip():
        raise ValueError("report_id is required")
    if not git_head.strip():
        raise ValueError("git_head is required")
    input_paths = {
        "retrieval_cases": retrieval_cases_path,
        "requirements": requirements_path,
        "baseline": baseline_path,
        "manual_review_workbook": manual_review_path,
        "final_adjudications": final_adjudications_path,
        "report_pdf": report_pdf_path,
    }
    missing_inputs = [name for name, path in input_paths.items() if not path.is_file()]
    if missing_inputs:
        raise FileNotFoundError(
            "missing Phase 1.5 inputs: " + ", ".join(missing_inputs)
        )

    with SessionLocal() as session:
        session.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        )
        actual_database = session.scalar(text("SELECT current_database()"))
        if actual_database != "esg_agent_demo":
            raise RuntimeError(
                "Phase 1.5 finalization requires active database esg_agent_demo"
            )
        formal_counts_before = capture_formal_table_counts(session)
        report_chunks = Repository(session).list_document_chunks(report_id=report_id)
        if not report_chunks:
            raise ValueError("report has no document chunks")
        first_contexts = load_shadow_contexts_from_cases(
            retrieval_cases_path,
            report_id=report_id,
            report_chunks=report_chunks,
            **RETRIEVAL_PARAMETERS,
        )
        second_contexts = load_shadow_contexts_from_cases(
            retrieval_cases_path,
            report_id=report_id,
            report_chunks=report_chunks,
            **RETRIEVAL_PARAMETERS,
        )
        first_hashes = _context_hashes(first_contexts)
        second_hashes = _context_hashes(second_contexts)
        all_requirement_ids = set(first_hashes) | set(second_hashes)
        mismatch_count = sum(
            first_hashes.get(requirement_id) != second_hashes.get(requirement_id)
            for requirement_id in all_requirement_ids
        )
        if mismatch_count:
            raise ValueError(f"deterministic context hash mismatch: {mismatch_count}")
        context_path = write_shadow_contexts(
            first_contexts,
            output=context_output,
        )
        formal_counts_after = capture_formal_table_counts(session)

    manifest_output, formal_state_output = _manifest_output_names(output_prefix)
    manifest_path = resolve_shadow_output(manifest_output)
    formal_state_path = resolve_shadow_output(formal_state_output)
    cases_path = resolve_shadow_output(f"{output_prefix}_cases.csv")
    summary_path = resolve_shadow_output(f"{output_prefix}_summary.json")
    report_path = resolve_shadow_output(f"{output_prefix}_report.md")

    implementation_files = {
        relative_path: fingerprint_file(
            PROJECT_ROOT / relative_path,
            project_root=PROJECT_ROOT,
        )
        for relative_path in IMPLEMENTATION_RELATIVE_PATHS
    }
    manifest = {
        "git_head": git_state["head"],
        "git_state": git_state,
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "retrieval_parameters": RETRIEVAL_PARAMETERS,
        "implementation_files": implementation_files,
        "files": {
            **{
                name: fingerprint_file(
                    path,
                    project_root=PROJECT_ROOT,
                )
                for name, path in input_paths.items()
            },
            "context_jsonl": fingerprint_file(
                context_path,
                project_root=PROJECT_ROOT,
            ),
        },
    }
    cases, loaded_contexts = load_comparison_inputs(
        retrieval_cases_path,
        context_path,
        report_id=report_id,
        expected_count=EXPECTED_CASE_COUNT,
    )
    context_audit = audit_contexts(
        loaded_contexts,
        report_id=report_id,
        report_total_pages=report_total_pages,
        expected_count=EXPECTED_CASE_COUNT,
    )
    run_metadata = {
        "git_head": git_state["head"],
        "git_dirty": git_state["dirty"],
        "git_status_sha256": git_state["status_sha256"],
        "input_manifest_path": (
            manifest_path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
        ),
        "retrieval_mode": RETRIEVAL_PARAMETERS["retrieval_mode"],
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        **RETRIEVAL_PARAMETERS,
    }
    summary = build_acceptance_summary(
        report_id=report_id,
        run_metadata=run_metadata,
        cases=cases,
        context_audit=context_audit,
        deterministic_hash_mismatch_count=mismatch_count,
        formal_table_counts_before=formal_counts_before,
        formal_table_counts_after=formal_counts_after,
        embedding_enabled=settings.embedding_enabled,
        expected_count=EXPECTED_CASE_COUNT,
        expected_evaluated_case_count=EXPECTED_EVALUATED_CASE_COUNT,
    )
    formal_state = {
        "transaction_isolation": "REPEATABLE READ",
        "transaction_read_only": True,
        "before": formal_counts_before,
        "after": formal_counts_after,
        "unchanged": formal_counts_before == formal_counts_after,
    }
    _write_cases(cases_path, cases)
    _write_json(summary_path, summary)
    _write_json(manifest_path, manifest)
    _write_json(formal_state_path, formal_state)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_acceptance_report(summary),
        encoding="utf-8",
    )
    return {
        **summary,
        "outputs": {
            "contexts": str(context_path),
            "cases": str(cases_path),
            "summary": str(summary_path),
            "input_manifest": str(manifest_path),
            "formal_state": str(formal_state_path),
            "report": str(report_path),
        },
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Finalize the offline hybrid shadow RAG Phase 1.5."
    )
    parser.add_argument("--report-id", required=True)
    parser.add_argument(
        "--retrieval-cases",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
    )
    parser.add_argument(
        "--manual-review-workbook",
        type=Path,
        default=DEFAULT_MANUAL_REVIEW,
    )
    parser.add_argument(
        "--final-adjudications",
        type=Path,
        default=DEFAULT_FINAL_ADJUDICATIONS,
    )
    parser.add_argument(
        "--report-pdf",
        type=Path,
        default=DEFAULT_REPORT_PDF,
    )
    parser.add_argument(
        "--context-output",
        default="tmp/embedding/envision_phase1_5_contexts.jsonl",
    )
    parser.add_argument(
        "--output-prefix",
        default="tmp/embedding/envision_phase1_5_acceptance",
    )
    parser.add_argument(
        "--report-total-pages",
        type=int,
        default=78,
    )
    parser.add_argument("--git-head", required=True)
    args = parser.parse_args(argv)
    result = finalize_phase1_5(
        report_id=args.report_id,
        retrieval_cases_path=args.retrieval_cases,
        requirements_path=args.requirements,
        baseline_path=args.baseline,
        manual_review_path=args.manual_review_workbook,
        final_adjudications_path=args.final_adjudications,
        report_pdf_path=args.report_pdf,
        context_output=args.context_output,
        output_prefix=args.output_prefix,
        report_total_pages=args.report_total_pages,
        git_head=args.git_head,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
