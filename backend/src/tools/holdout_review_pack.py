from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Mapping
from pathlib import Path

from src.reports.profile import load_report_profile
from src.standards.compilation_guardrails import get_compilation_guardrails


ROUTE_IMPROVEMENT_COLUMNS = [
    "requirement_id",
    "requirement_text",
    "verdict",
    "review_status",
    "source_pdf_pages",
    "rationale",
    "missing_items",
    "issue_type",
    "evidence_kind",
    "correct_pdf_pages",
    "suggested_profile_route",
    "route_failure_reason",
    "before_verdict",
    "before_review_status",
    "before_source_pdf_pages",
    "before_candidate_pdf_pages",
    "before_candidate_page_source",
    "profile_candidate_pdf_pages",
    "route_status",
    "evidence_preview",
]

REVIEW_PACK_COLUMNS = [
    "requirement_id",
    "requirement_text",
    "verdict",
    "review_status",
    "candidate_pdf_pages",
    "source_pdf_pages",
    "evidence_type",
    "rationale",
    "missing_items",
    "guardrail_items",
    "selection_bucket",
    "selection_theme",
    "selection_reason",
    "issue_type",
    "evidence_kind",
    "correct_pdf_pages",
    "suggested_profile_route",
    "current_route_status",
    "manual_check_required",
    "manual_check_focus",
    "manual_label",
    "correct_source_pdf_pages",
    "suggested_verdict",
    "review_note",
    "evidence_preview",
]


def build_route_improvement_rows(
    diagnosis_csv: Path,
    first_pass_csv: Path,
    report_profile_path: Path | None = None,
    requirement_texts: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    diagnosis_rows = _read_csv(diagnosis_csv)
    first_rows = _group_by_requirement(_read_csv(first_pass_csv))
    profile_routes = _profile_candidate_pages(report_profile_path)
    output: list[dict[str, str]] = []
    for diagnosis in diagnosis_rows:
        requirement_id = diagnosis["requirement_id"]
        rows = first_rows.get(requirement_id, [])
        source_pages = sorted(
            {row["source_pdf_page"] for row in rows if row.get("source_pdf_page")},
            key=int,
        )
        candidate_pages = _first_non_empty(rows, "candidate_pdf_pages")
        profile_candidate_pages = profile_routes.get(requirement_id, "[]")
        correct_pages = diagnosis.get("correct_pdf_pages", "[]")
        output.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": _first_non_empty(rows, "requirement_text")
                or (requirement_texts or {}).get(requirement_id, ""),
                "verdict": _first_non_empty(rows, "verdict") or "missing",
                "review_status": _first_non_empty(rows, "review_status") or "missing",
                "source_pdf_pages": json.dumps([int(page) for page in source_pages], ensure_ascii=False),
                "rationale": _first_non_empty(rows, "rationale"),
                "missing_items": _first_non_empty(rows, "missing_items"),
                "issue_type": diagnosis.get("issue_type", ""),
                "evidence_kind": diagnosis.get("evidence_kind", ""),
                "correct_pdf_pages": correct_pages,
                "suggested_profile_route": diagnosis.get("suggested_profile_route", correct_pages),
                "route_failure_reason": diagnosis.get("route_failure_reason", ""),
                "before_verdict": _first_non_empty(rows, "verdict") or "missing",
                "before_review_status": _first_non_empty(rows, "review_status") or "missing",
                "before_source_pdf_pages": json.dumps(source_pages, ensure_ascii=False),
                "before_candidate_pdf_pages": candidate_pages,
                "before_candidate_page_source": _first_non_empty(rows, "candidate_page_source"),
                "profile_candidate_pdf_pages": profile_candidate_pages,
                "route_status": _route_status(candidate_pages, source_pages, correct_pages, profile_candidate_pages),
                "evidence_preview": _first_non_empty(rows, "evidence_preview"),
            }
        )
    return output


def write_route_improvement_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROUTE_IMPROVEMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def build_review_pack_rows(route_improvement_csv: Path) -> list[dict[str, str]]:
    rows = _read_csv(route_improvement_csv)
    output: list[dict[str, str]] = []
    for row in rows:
        leaf_missing_items, guardrail_items = _split_missing_items(
            row["requirement_id"],
            row.get("missing_items", ""),
        )
        expected_no_evidence = _is_expected_no_evidence_row(row)
        issue_type = "acceptable" if expected_no_evidence else row.get("issue_type", "")
        evidence_kind = "" if expected_no_evidence else row.get("evidence_kind", "")
        focus = "route_and_preview"
        if expected_no_evidence:
            focus = "no_evidence_boundary"
        elif issue_type == "false_disclosed":
            focus = "false_disclosed_boundary"
        output.append(
            {
                "requirement_id": row["requirement_id"],
                "requirement_text": row.get("requirement_text", ""),
                "verdict": row.get("verdict", ""),
                "review_status": row.get("review_status", ""),
                "candidate_pdf_pages": row.get("before_candidate_pdf_pages", "[]"),
                "source_pdf_pages": row.get("source_pdf_pages", "[]"),
                "evidence_type": row.get("evidence_type", ""),
                "rationale": row.get("rationale", ""),
                "missing_items": leaf_missing_items,
                "guardrail_items": guardrail_items,
                "selection_bucket": row.get("selection_bucket", ""),
                "selection_reason": row.get("selection_reason", ""),
                "issue_type": issue_type,
                "evidence_kind": evidence_kind,
                "correct_pdf_pages": row.get("correct_pdf_pages", ""),
                "suggested_profile_route": row.get("suggested_profile_route", ""),
                "current_route_status": row.get("route_status", ""),
                "manual_check_required": "true",
                "manual_check_focus": focus,
                "manual_label": "",
                "correct_source_pdf_pages": "",
                "suggested_verdict": "",
                "review_note": "",
                "evidence_preview": row.get("evidence_preview", ""),
            }
        )
    return output


def build_stratified_review_pack_rows(
    first_pass_csv: Path,
    selection_csv: Path,
    requirement_texts: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    first_rows = _group_by_requirement(_read_csv(first_pass_csv))
    selection_rows = _read_csv(selection_csv)
    output: list[dict[str, str]] = []
    for selection in selection_rows:
        requirement_id = selection["requirement_id"]
        rows = first_rows.get(requirement_id, [])
        if not rows:
            raise ValueError(f"selected requirement missing from first-pass CSV: {requirement_id}")
        source_pages = sorted(
            {
                page
                for row in rows
                for page in _parse_page_values(row.get("source_pdf_page", ""))
            }
        )
        candidate_pages = sorted(
            {
                page
                for row in rows
                for page in _parse_page_values(row.get("candidate_pdf_pages", ""))
            }
        )
        evidence_types = sorted(
            {(row.get("evidence_type") or "").strip() for row in rows} - {""}
        )
        leaf_missing_items, guardrail_items = _split_missing_items(
            requirement_id,
            _first_non_empty(rows, "missing_items"),
        )
        verdict = _first_non_empty(rows, "verdict")
        no_evidence = verdict == "unknown" and not source_pages
        output.append(
            {
                "requirement_id": requirement_id,
                "requirement_text": _first_non_empty(rows, "requirement_text")
                or (requirement_texts or {}).get(requirement_id, ""),
                "verdict": verdict,
                "review_status": _first_non_empty(rows, "review_status"),
                "candidate_pdf_pages": json.dumps(candidate_pages, ensure_ascii=False),
                "source_pdf_pages": json.dumps(source_pages, ensure_ascii=False),
                "evidence_type": "" if no_evidence else json.dumps(evidence_types, ensure_ascii=False),
                "rationale": _first_non_empty(rows, "rationale"),
                "missing_items": leaf_missing_items,
                "guardrail_items": guardrail_items,
                "selection_bucket": selection.get("selection_bucket", ""),
                "selection_theme": selection.get("selection_theme", ""),
                "selection_reason": selection.get("selection_reason", ""),
                "issue_type": "",
                "evidence_kind": "" if no_evidence else selection.get("evidence_kinds", "[]"),
                "correct_pdf_pages": "",
                "suggested_profile_route": "",
                "current_route_status": selection.get("route_status", ""),
                "manual_check_required": "true",
                "manual_check_focus": "no_evidence_boundary" if no_evidence else "evidence_and_verdict",
                "manual_label": "",
                "correct_source_pdf_pages": "",
                "suggested_verdict": "",
                "review_note": "",
                "evidence_preview": "" if no_evidence else _first_non_empty(rows, "evidence_preview"),
            }
        )
    return output


def _split_missing_items(requirement_id: str, raw_missing_items: str) -> tuple[str, str]:
    try:
        parsed = json.loads(raw_missing_items or "[]")
    except json.JSONDecodeError:
        parsed = []
    missing_items = [str(item) for item in parsed] if isinstance(parsed, list) else []
    guardrail_templates = {
        template
        for guardrail in get_compilation_guardrails(requirement_id)
        for template in guardrail.missing_item_templates
    }
    leaf_items = [item for item in missing_items if item not in guardrail_templates]
    guardrail_items = [item for item in missing_items if item in guardrail_templates]
    return (
        json.dumps(leaf_items, ensure_ascii=False),
        json.dumps(guardrail_items, ensure_ascii=False),
    )


def _is_expected_no_evidence_row(row: dict[str, str]) -> bool:
    return (
        row.get("before_verdict") == "unknown"
        and row.get("before_source_pdf_pages", "") in {"", "[]"}
        and row.get("correct_pdf_pages", "") in {"", "[]"}
        and row.get("profile_candidate_pdf_pages", "") in {"", "[]"}
    )


def write_review_pack_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_PACK_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _group_by_requirement(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["requirement_id"], []).append(row)
    return grouped


def _first_non_empty(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = row.get(field, "")
        if value:
            return value
    return ""


def _parse_page_values(raw: str) -> list[int]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    values = parsed if isinstance(parsed, list) else [parsed]
    pages: list[int] = []
    for value in values:
        try:
            pages.append(int(value))
        except (TypeError, ValueError):
            continue
    return pages


def _profile_candidate_pages(report_profile_path: Path | None) -> dict[str, str]:
    if report_profile_path is None:
        return {}
    profile = load_report_profile(report_profile_path)
    return {
        requirement_id: json.dumps(route.candidate_pdf_pages, ensure_ascii=False)
        for requirement_id, route in profile.requirement_routes.items()
    }


def _route_status(
    candidate_pages: str,
    source_pages: list[str],
    correct_pages: str,
    profile_candidate_pages: str = "[]",
) -> str:
    effective_candidate_pages = candidate_pages if candidate_pages and candidate_pages != "[]" else profile_candidate_pages
    if not effective_candidate_pages or effective_candidate_pages == "[]":
        return "missing_candidate"
    if not source_pages:
        return "candidate_without_evidence"
    try:
        correct = {str(page) for page in json.loads(correct_pages or "[]")}
    except json.JSONDecodeError:
        correct = set()
    if correct and not correct.intersection(source_pages):
        return "wrong_source"
    return "candidate_with_evidence"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a stratified holdout review pack.")
    parser.add_argument("first_pass_csv", type=Path)
    parser.add_argument("selection_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()

    from src.standards.gri import GRIAdapter

    checklist_path = Path(__file__).resolve().parents[2] / "data" / "manifests" / "gri_requirement_checklist.json"
    requirement_texts = {
        requirement.requirement_id: requirement.requirement_text
        for requirement in GRIAdapter(checklist_path).load_requirements()
    }
    rows = build_stratified_review_pack_rows(
        args.first_pass_csv,
        args.selection_csv,
        requirement_texts=requirement_texts,
    )
    write_review_pack_rows(rows, args.output_csv)


if __name__ == "__main__":
    main()
