from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


DIAGNOSIS_COLUMNS = [
    "requirement_id",
    "verdict",
    "review_status",
    "issue_type",
    "correct_pdf_pages",
    "evidence_kind",
    "current_source_pdf_pages",
    "current_candidate_pdf_pages",
    "current_retrieval_strategy",
    "route_failure_reason",
    "suggested_profile_route",
    "evidence_preview",
]


def build_recall_diagnosis_rows(
    first_pass_csv: Path,
    manual_gold: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    with first_pass_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["requirement_id"], []).append(row)

    diagnosis_rows: list[dict[str, str]] = []
    for requirement_id, gold in manual_gold.items():
        source_rows = grouped.get(requirement_id, [])
        current_sources = sorted(
            {
                int(float(row["source_pdf_page"]))
                for row in source_rows
                if row.get("source_pdf_page")
            }
        )
        candidate_pages = _first_non_empty(source_rows, "candidate_pdf_pages")
        retrieval_strategy = _first_non_empty(source_rows, "retrieval_strategy")
        evidence_preview = _first_non_empty(source_rows, "evidence_preview")
        verdict = _first_non_empty(source_rows, "verdict") or "missing"
        review_status = _first_non_empty(source_rows, "review_status") or "missing"

        correct_pages = gold.get("correct_pdf_pages", [])
        diagnosis_rows.append(
            {
                "requirement_id": requirement_id,
                "verdict": verdict,
                "review_status": review_status,
                "issue_type": str(gold.get("issue_type", "")),
                "correct_pdf_pages": json.dumps(correct_pages, ensure_ascii=False),
                "evidence_kind": str(gold.get("evidence_kind", "")),
                "current_source_pdf_pages": json.dumps(current_sources, ensure_ascii=False),
                "current_candidate_pdf_pages": candidate_pages,
                "current_retrieval_strategy": retrieval_strategy,
                "route_failure_reason": _route_failure_reason(candidate_pages, current_sources, gold),
                "suggested_profile_route": json.dumps(correct_pages, ensure_ascii=False),
                "evidence_preview": evidence_preview,
            }
        )
    return diagnosis_rows


def write_recall_diagnosis_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DIAGNOSIS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _first_non_empty(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = row.get(field, "")
        if value:
            return value
    return ""


def _route_failure_reason(
    candidate_pages_text: str,
    current_sources: list[int],
    gold: dict[str, Any],
) -> str:
    correct_pages = set(gold.get("correct_pdf_pages", []))
    if not candidate_pages_text or candidate_pages_text in {"[]", ""}:
        return "candidate_pages_missing"
    if not current_sources:
        return "candidate_pages_present_keyword_miss"
    if current_sources and not correct_pages.intersection(current_sources):
        return "wrong_source_page"
    return "evidence_found_matrix_conservative"
