from __future__ import annotations

import csv
import json
from pathlib import Path


ROUTE_IMPROVEMENT_COLUMNS = [
    "requirement_id",
    "issue_type",
    "evidence_kind",
    "correct_pdf_pages",
    "suggested_profile_route",
    "before_verdict",
    "before_review_status",
    "before_source_pdf_pages",
    "before_candidate_pdf_pages",
    "route_status",
    "evidence_preview",
]


def build_route_improvement_rows(diagnosis_csv: Path, first_pass_csv: Path) -> list[dict[str, str]]:
    diagnosis_rows = _read_csv(diagnosis_csv)
    first_rows = _group_by_requirement(_read_csv(first_pass_csv))
    output: list[dict[str, str]] = []
    for diagnosis in diagnosis_rows:
        requirement_id = diagnosis["requirement_id"]
        rows = first_rows.get(requirement_id, [])
        source_pages = sorted({row["source_pdf_page"] for row in rows if row.get("source_pdf_page")})
        candidate_pages = _first_non_empty(rows, "candidate_pdf_pages")
        correct_pages = diagnosis.get("correct_pdf_pages", "[]")
        output.append(
            {
                "requirement_id": requirement_id,
                "issue_type": diagnosis.get("issue_type", ""),
                "evidence_kind": diagnosis.get("evidence_kind", ""),
                "correct_pdf_pages": correct_pages,
                "suggested_profile_route": diagnosis.get("suggested_profile_route", correct_pages),
                "before_verdict": _first_non_empty(rows, "verdict") or "missing",
                "before_review_status": _first_non_empty(rows, "review_status") or "missing",
                "before_source_pdf_pages": json.dumps(source_pages, ensure_ascii=False),
                "before_candidate_pdf_pages": candidate_pages,
                "route_status": _route_status(candidate_pages, source_pages, correct_pages),
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


def _route_status(candidate_pages: str, source_pages: list[str], correct_pages: str) -> str:
    if not candidate_pages or candidate_pages == "[]":
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
