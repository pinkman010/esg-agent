from __future__ import annotations

import csv
from pathlib import Path


PREVIEW_SAMPLE_COLUMNS = [
    "requirement_id",
    "verdict",
    "source_pdf_page",
    "candidate_page_source",
    "evidence_type",
    "preview_anchor_status",
    "expected_anchors",
    "evidence_preview",
]


def build_preview_sample_rows(source_csv: Path, anchors: dict[str, list[str]]) -> list[dict[str, str]]:
    with source_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    sampled: list[dict[str, str]] = []
    for row in rows:
        requirement_id = row.get("requirement_id", "")
        expected = anchors.get(requirement_id)
        if expected is None:
            continue
        preview = row.get("evidence_preview", "")
        status = "anchor_found" if any(anchor in preview for anchor in expected) else "missing_anchor"
        sampled.append(
            {
                "requirement_id": requirement_id,
                "verdict": row.get("verdict", ""),
                "source_pdf_page": row.get("source_pdf_page", ""),
                "candidate_page_source": row.get("candidate_page_source", ""),
                "evidence_type": row.get("evidence_type", ""),
                "preview_anchor_status": status,
                "expected_anchors": "|".join(expected),
                "evidence_preview": preview,
            }
        )
    return sampled


def write_preview_sample_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREVIEW_SAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
