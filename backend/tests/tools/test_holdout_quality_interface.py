from src.tools.first_pass_quality import summarize_quality


def test_holdout_quality_accepts_empty_gold_fields_without_running_holdout():
    rows = [
        {
            "requirement_id": "HOLDOUT supplier screening percentage",
            "verdict": "disclosed",
            "source_pdf_page": "67",
            "manual_label": "",
            "correct_pdf_pages": "",
            "suggested_verdict": "",
            "issue_type": "",
        }
    ]

    summary = summarize_quality(rows, rows)

    assert summary.false_disclosed_count == 0
    assert summary.wrong_source_page_count == 0
