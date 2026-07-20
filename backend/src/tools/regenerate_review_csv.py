from __future__ import annotations

import argparse
import csv
import hashlib
import json
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.db.repositories import Repository
from src.db.session import get_engine
from src.domain.enums import RunStatus
from src.domain.models import Report
from src.tools.review_csv_export import REVIEW_CSV_FIELDS, export_review_rows


@dataclass
class RepositoryContext(AbstractContextManager):
    repository: Repository
    session: Session | None

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.session is not None:
            self.session.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate review CSV for a single ESG report.")
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--diff-summary-output", type=Path)
    parser.add_argument("--scope-summary-output", type=Path)
    parser.add_argument("--manual-review-workbook", type=Path)
    parser.add_argument("--report-total-pages", type=int, default=78)
    parser.add_argument("--confirm-llm", action="store_true", default=False)
    parser.add_argument("--enable-ocr", action="store_true", default=False)
    parser.add_argument("--ocr-pages", type=int, action="append", default=[])
    return parser.parse_args(argv)


def filter_eligible_assessments(assessments: list[Any]) -> list[Any]:
    return [
        assessment
        for assessment in assessments
        if _get(assessment, "requirement_type") != "compilation_requirement"
        and not _looks_like_compilation_requirement(str(_get(assessment, "requirement_id", "")))
    ]


def write_review_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run_single_report_regeneration(args: argparse.Namespace) -> list[Any]:
    with open_repository_session() as context:
        report_id = _run_report_id(args.report_id)
        file_hash = _sha256(args.pdf)
        context.repository.create_report(
            Report(
                report_id=report_id,
                original_filename=args.pdf.name,
                stored_path=str(args.pdf),
                file_hash=file_hash,
            )
        )
        workflow = build_workflow(args, context.repository)
        run = workflow.run(
            report_id,
            args.pdf,
            file_hash,
            confirm_llm=args.confirm_llm,
            enable_ocr=args.enable_ocr,
            ocr_pages=args.ocr_pages,
        )
        status_value = getattr(getattr(run, "status", None), "value", getattr(run, "status", None))
        if status_value != RunStatus.COMPLETED.value:
            error_message = getattr(run, "error_message", None)
            raise RuntimeError(f"regeneration workflow failed: {error_message or status_value}")
        return context.repository.list_assessments_by_run(run.run_id)


def build_workflow(args: argparse.Namespace, repository: Repository):
    from src.agents.disclosure_agent import DisclosureAgent
    from src.services.document_parser import DocumentParser
    from src.standards.gri import GRIAdapter
    from src.workflows.single_report_workflow import SingleReportWorkflow

    data_root = Path(__file__).resolve().parents[2] / "data"
    return SingleReportWorkflow(
        repository,
        DocumentParser(),
        GRIAdapter(
            getattr(args, "requirements", None)
            or data_root / "manifests" / "gri_requirement_checklist.json"
        ),
        DisclosureAgent(),
        requirement_pack_path=data_root / "manifests" / "gri_requirement_pack.json",
        report_profile_path=args.profile,
    )


def open_repository_session() -> RepositoryContext:
    engine = get_engine()
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = SessionLocal()
    return RepositoryContext(Repository(session), session)


def write_audit(path: Path, review_csv: Path, report_total_pages: int) -> None:
    from src.tools.review_csv_audit import audit_review_csv

    result = audit_review_csv(review_csv, report_total_pages=report_total_pages)
    payload = {"ok": result.ok, **asdict(result)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not result.ok:
        raise SystemExit(1)


def write_diff_summary(
    path: Path,
    baseline: Path,
    regenerated: Path,
    *,
    manual_review_workbook: Path | None = None,
) -> None:
    from src.tools.first_pass_quality import compare_first_pass_to_after_rules

    result = compare_first_pass_to_after_rules(baseline, regenerated)
    payload = asdict(result)
    if manual_review_workbook is not None:
        from src.services.ai_evaluation_service import load_manual_review_baseline

        manual = load_manual_review_baseline(manual_review_workbook).records
        payload.update(
            compare_manual_review_regression(
                manual,
                _read_review_csv(baseline),
                _read_review_csv(regenerated),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_scope_summary(
    path: Path,
    requirements_path: Path,
    rows: list[dict[str, str]],
) -> None:
    from src.standards.gri import GRIAdapter

    summary = GRIAdapter(requirements_path).get_scope_summary()
    unique_ids = {row["requirement_id"] for row in rows}
    summary.update(
        {
            "exported_row_count": len(rows),
            "unique_assessment_requirement_id_count": len(unique_ids),
            "global_fallback_count": sum(
                row.get("retrieval_strategy") == "global_fallback" for row in rows
            ),
        }
    )
    if len(unique_ids) != summary["independent_assessment_count"]:
        raise ValueError(
            "regenerated requirement count does not match independent assessment scope"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    assessments = run_single_report_regeneration(args)
    eligible = filter_eligible_assessments(assessments)
    if args.requirements is not None:
        from src.standards.gri import GRIAdapter

        tasks = GRIAdapter(args.requirements).build_tasks(
            run_id="regeneration",
            report_id=args.report_id,
        )
        eligible = enrich_assessments_with_tasks(eligible, tasks)
    rows = export_review_rows(eligible)
    write_review_csv(args.output, rows)
    if args.audit_output:
        write_audit(args.audit_output, args.output, args.report_total_pages)
    if args.baseline and args.diff_summary_output:
        write_diff_summary(
            args.diff_summary_output,
            args.baseline,
            args.output,
            manual_review_workbook=args.manual_review_workbook,
        )
    if args.scope_summary_output:
        if args.requirements is None:
            raise ValueError("--scope-summary-output requires --requirements")
        write_scope_summary(args.scope_summary_output, args.requirements, rows)


def enrich_assessments_with_tasks(
    assessments: list[Any],
    tasks: list[Any],
) -> list[dict[str, Any]]:
    tasks_by_requirement = {
        str(_get(task, "requirement_id")): task for task in tasks
    }
    enriched: list[dict[str, Any]] = []
    for assessment in assessments:
        requirement_id = str(_get(assessment, "requirement_id"))
        task = tasks_by_requirement.get(requirement_id)
        if task is None:
            raise ValueError(f"v2 task missing for assessment: {requirement_id}")
        if isinstance(assessment, dict):
            item = dict(assessment)
        elif hasattr(assessment, "model_dump"):
            item = assessment.model_dump(mode="python")
        else:
            item = dict(vars(assessment))
        item.update(
            {
                "structure_status": _get(task, "structure_status"),
                "source_requirement_text": _get(task, "source_requirement_text"),
                "effective_requirement_text": _get(task, "requirement_text"),
            }
        )
        enriched.append(item)
    return enriched


def compare_manual_review_regression(
    manual_records: list[Any],
    baseline_rows: list[dict[str, str]],
    current_rows: list[dict[str, str]],
) -> dict[str, Any]:
    baseline = _aggregate_review_rows(baseline_rows)
    current = _aggregate_review_rows(current_rows)
    comparable = [
        record
        for record in manual_records
        if _get(record, "suggested_verdict") is not None
        and _get(record, "requirement_id") in baseline
        and _get(record, "requirement_id") in current
    ]

    def failures(dataset: dict[str, dict[str, Any]]) -> tuple[set[str], set[str]]:
        false_disclosed: set[str] = set()
        wrong_pages: set[str] = set()
        for record in comparable:
            requirement_id = str(_get(record, "requirement_id"))
            manual_verdict = _get(record, "suggested_verdict")
            manual_verdict_value = _get(manual_verdict, "value", manual_verdict)
            item = dataset[requirement_id]
            if item["verdict"] == "disclosed" and manual_verdict_value != "disclosed":
                false_disclosed.add(requirement_id)
            correct_pages = set(_get(record, "correct_pdf_pages", []))
            if (
                item["verdict"] == manual_verdict_value
                and correct_pages
                and item["pages"]
                and any(page not in correct_pages for page in item["pages"])
            ):
                wrong_pages.add(requirement_id)
        return false_disclosed, wrong_pages

    baseline_false, baseline_wrong = failures(baseline)
    current_false, current_wrong = failures(current)
    new_false = sorted(current_false - baseline_false)
    new_wrong = sorted(current_wrong - baseline_wrong)
    return {
        "manual_gold_available": True,
        "manual_gold_comparable_count": len(comparable),
        "baseline_manual_false_disclosed_count": len(baseline_false),
        "baseline_manual_wrong_source_page_count": len(baseline_wrong),
        "current_manual_false_disclosed_count": len(current_false),
        "current_manual_wrong_source_page_count": len(current_wrong),
        "new_false_disclosed_count": len(new_false),
        "new_wrong_source_page_count": len(new_wrong),
        "new_false_disclosed_requirement_ids": new_false,
        "new_wrong_source_page_requirement_ids": new_wrong,
    }


def _read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _aggregate_review_rows(
    rows: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for row in rows:
        requirement_id = row.get("requirement_id", "").strip()
        if not requirement_id:
            continue
        item = aggregated.setdefault(
            requirement_id,
            {"verdict": row.get("verdict", "").strip(), "pages": set()},
        )
        page = row.get("source_pdf_page", "").strip()
        if page:
            item["pages"].add(int(page))
    return aggregated


def _looks_like_compilation_requirement(requirement_id: str) -> bool:
    if "." in requirement_id:
        return True
    parts = requirement_id.replace("GRI ", "").split("-")
    return len(parts) >= 4 and any("." in part for part in parts)


def _run_report_id(report_id: str) -> str:
    return f"{report_id}-regeneration-{uuid4().hex[:12]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


if __name__ == "__main__":
    main()
