import json
from pathlib import Path

from src.tools.calibrate_report_profile import calibrate_profile_file


def test_calibrate_profile_file_uses_reviewed_correct_pages(tmp_path: Path):
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "report_id": "sample",
                "company_name": "Sample",
                "report_year": 2024,
                "pdf_file": "sample.pdf",
                "total_pdf_pages": 52,
                "page_numbering": {"report_index_pdf_page": 50, "report_index_report_page": 96, "total_pdf_pages": 52},
                "gri_index": {"pdf_pages": [50, 51]},
                "kpi_tables": [],
                "sections": [],
                "index_note_pages": [],
                "assurance_pages": [],
                "requirement_routes": {
                    "GRI 305-3-a": {"candidate_pdf_pages": [25], "kpi_table_pages": [], "metric_terms": ["范围3"]}
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    reviewed = tmp_path / "reviewed.csv"
    reviewed.write_text(
        "requirement_id,correct_pdf_pages\n"
        'GRI 305-3-a,"[26]"\n'
        'GRI 418-1-a,"[]"\n',
        encoding="utf-8",
    )
    output = tmp_path / "calibrated.json"

    calibrate_profile_file(profile, reviewed, output)

    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["requirement_routes"]["GRI 305-3-a"]["candidate_pdf_pages"] == [26]
    assert result["requirement_routes"]["GRI 418-1-a"]["candidate_pdf_pages"] == []
