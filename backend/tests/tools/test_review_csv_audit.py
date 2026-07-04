import csv
from pathlib import Path

from src.tools.review_csv_audit import audit_review_csv


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "requirement_id",
        "verdict",
        "review_status",
        "retrieval_strategy",
        "evidence_type",
        "source_pdf_page",
        "source_report_page",
        "page_label",
        "candidate_pdf_pages",
        "quality_flags",
        "requires_ocr",
        "needs_ocr_or_vlm",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_review_csv_audit_reports_hard_gate_failures(tmp_path):
    path = tmp_path / "review.csv"
    write_csv(
        path,
        [
            {
                "requirement_id": "GRI 305-2-a",
                "verdict": "disclosed",
                "review_status": "not_required",
                "retrieval_strategy": "index_page_bounded",
                "evidence_type": "substantive",
                "source_pdf_page": "3",
                "source_report_page": "2",
                "page_label": "PDF 第 3 页 / 报告页 2",
                "candidate_pdf_pages": "[20, 63]",
                "quality_flags": '["digital_text"]',
                "requires_ocr": "False",
                "needs_ocr_or_vlm": "False",
            },
            {
                "requirement_id": "GRI 304-4-a",
                "verdict": "partially_disclosed",
                "review_status": "needs_manual_review",
                "retrieval_strategy": "index_page_bounded",
                "evidence_type": "omission_note",
                "source_pdf_page": "74",
                "source_report_page": "73",
                "page_label": "PDF 第 74 页 / 报告页 73",
                "candidate_pdf_pages": "[74]",
                "quality_flags": '["digital_text"]',
                "requires_ocr": "False",
                "needs_ocr_or_vlm": "False",
            },
            {
                "requirement_id": "GRI 205-3-b",
                "verdict": "disclosed",
                "review_status": "not_required",
                "retrieval_strategy": "index_page_bounded",
                "evidence_type": "substantive",
                "source_pdf_page": "68",
                "source_report_page": "67",
                "page_label": "PDF 第 68 页 / 报告页 67",
                "candidate_pdf_pages": "[68]",
                "quality_flags": '["digital_text"]',
                "requires_ocr": "False",
                "needs_ocr_or_vlm": "False",
            },
        ],
    )

    result = audit_review_csv(path, report_total_pages=78)

    assert "GRI 305-2-a uses forbidden PDF page 3" in result.errors
    assert "GRI 304-4-a omission_note cannot be partially_disclosed" in result.errors
    assert "GRI 205-3-b KPI page 68 missing complex_table" in result.errors
