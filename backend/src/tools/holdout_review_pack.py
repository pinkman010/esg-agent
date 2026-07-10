from __future__ import annotations

import csv
import json
from pathlib import Path

from src.reports.profile import load_report_profile


ROUTE_IMPROVEMENT_COLUMNS = [
    "requirement_id",
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
) -> list[dict[str, str]]:
    diagnosis_rows = _read_csv(diagnosis_csv)
    first_rows = _group_by_requirement(_read_csv(first_pass_csv))
    profile_routes = _profile_candidate_pages(report_profile_path)
    output: list[dict[str, str]] = []
    for diagnosis in diagnosis_rows:
        requirement_id = diagnosis["requirement_id"]
        rows = first_rows.get(requirement_id, [])
        source_pages = sorted({row["source_pdf_page"] for row in rows if row.get("source_pdf_page")})
        candidate_pages = _first_non_empty(rows, "candidate_pdf_pages")
        profile_candidate_pages = profile_routes.get(requirement_id, "[]")
        correct_pages = diagnosis.get("correct_pdf_pages", "[]")
        output.append(
            {
                "requirement_id": requirement_id,
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
