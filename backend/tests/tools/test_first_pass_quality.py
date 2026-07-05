import csv
from pathlib import Path

from src.tools.first_pass_quality import compare_first_pass_to_after_rules


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_first_pass_quality_counts_manual_gold_fields(tmp_path: Path):
    current = tmp_path / "current.csv"
    after = tmp_path / "after.csv"
    write_csv(
        current,
        [
            {
                "requirement_id": "GRI 414-1-a",
                "verdict": "unknown",
                "source_pdf_page": "",
                "manual_label": "漏检",
                "correct_pdf_pages": "[67]",
                "suggested_verdict": "disclosed",
                "issue_type": "missed_evidence",
            },
            {
                "requirement_id": "GRI 408-1-a-ii",
                "verdict": "disclosed",
                "source_pdf_page": "32",
                "manual_label": "误升",
                "correct_pdf_pages": "[32, 52, 53]",
                "suggested_verdict": "partially_disclosed",
                "issue_type": "false_disclosed",
            },
            {
                "requirement_id": "GRI 413-1-a-v",
                "verdict": "partially_disclosed",
                "source_pdf_page": "42",
                "manual_label": "证据页不完整",
                "correct_pdf_pages": "[14, 42, 43, 44]",
                "suggested_verdict": "partially_disclosed",
                "issue_type": "wrong_source_page",
            },
        ],
    )
    write_csv(
        after,
        [
            {"requirement_id": "GRI 414-1-a", "verdict": "disclosed", "source_pdf_page": "67"},
            {"requirement_id": "GRI 408-1-a-ii", "verdict": "partially_disclosed", "source_pdf_page": "32"},
            {"requirement_id": "GRI 413-1-a-v", "verdict": "partially_disclosed", "source_pdf_page": "14"},
        ],
    )

    result = compare_first_pass_to_after_rules(current, after)

    assert result.first_pass_unknown_count == 1
    assert result.unknown_leakage_count == 1
    assert result.false_disclosed_count == 1
    assert result.wrong_source_page_count == 1
    assert result.after_rules_delta_disclosed == 0
