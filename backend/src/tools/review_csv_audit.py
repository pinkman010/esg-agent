import csv
import json
from dataclasses import dataclass, field
from dataclasses import asdict
from pathlib import Path


@dataclass
class ReviewCsvAuditResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _loads_list(raw: str) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def audit_review_csv(path: str | Path, report_total_pages: int) -> ReviewCsvAuditResult:
    result = ReviewCsvAuditResult()
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        requirement_id = row.get("requirement_id", "")
        verdict = row.get("verdict", "")
        review_status = row.get("review_status", "")
        retrieval_strategy = row.get("retrieval_strategy", "")
        evidence_type = row.get("evidence_type", "")
        source_pdf_page = row.get("source_pdf_page", "")
        page_label = row.get("page_label", "")
        quality_flags = _loads_list(row.get("quality_flags", ""))
        candidate_pdf_pages = _loads_list(row.get("candidate_pdf_pages", ""))

        if retrieval_strategy == "global_fallback":
            result.errors.append(f"{requirement_id} uses global_fallback")

        if "?" in page_label:
            result.errors.append(f"{requirement_id} page_label contains '?'")

        for candidate_page in candidate_pdf_pages:
            if isinstance(candidate_page, int) and candidate_page > report_total_pages:
                result.errors.append(f"{requirement_id} candidate page {candidate_page} exceeds report total pages")

        if source_pdf_page:
            source_page_int = int(source_pdf_page)
            if source_page_int > report_total_pages:
                result.errors.append(f"{requirement_id} source page {source_page_int} exceeds report total pages")
            if requirement_id.startswith("GRI 305") and source_page_int == 3:
                result.errors.append(f"{requirement_id} uses forbidden PDF page 3")
            if source_page_int in {63, 65, 66, 67, 68} and "complex_table" not in quality_flags:
                result.errors.append(f"{requirement_id} KPI page {source_page_int} missing complex_table")
            if source_page_int == 77:
                requires_ocr = row.get("requires_ocr", "").lower() == "true"
                needs_ocr_or_vlm = row.get("needs_ocr_or_vlm", "").lower() == "true"
                if not (requires_ocr or needs_ocr_or_vlm):
                    result.errors.append(f"{requirement_id} assurance page 77 missing OCR/VLM risk flag")

        if evidence_type == "omission_note" and verdict != "unknown":
            result.errors.append(f"{requirement_id} omission_note cannot be {verdict}")

        if verdict == "disclosed" and review_status != "not_required":
            result.errors.append(f"{requirement_id} disclosed must be not_required")
        if verdict in {"partially_disclosed", "unknown"} and review_status != "needs_manual_review":
            result.errors.append(f"{requirement_id} {verdict} must be needs_manual_review")

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Audit review CSV hard gates.")
    parser.add_argument("review_csv", type=Path)
    parser.add_argument("--report-total-pages", type=int, required=True)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    result = audit_review_csv(args.review_csv, report_total_pages=args.report_total_pages)
    payload = {"ok": result.ok, **asdict(result)}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
