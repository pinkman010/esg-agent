import json
from pathlib import Path

import pytest

from src.reports.profile_resolver import (
    ReportProfileResolutionError,
    ReportProfileResolver,
)


PROFILE_ROOT = Path("data/reports/profiles")


def test_resolves_envision_profile_from_declared_filename():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename="Envision Energy 2024-zh.pdf",
        page_count=78,
    )

    assert result == PROFILE_ROOT / "envision_2024.json"


def test_resolves_goldwind_profile_from_declared_filename():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename="Goldwind 2024-zh.pdf",
        page_count=52,
    )

    assert result == PROFILE_ROOT / "goldwind_2024.json"


def test_filename_matching_normalizes_case_unicode_whitespace_and_path():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename=" uploads/  ＧＯＬＤＷＩＮＤ 2024-ZH.PDF  ",
        page_count=52,
    )

    assert result == PROFILE_ROOT / "goldwind_2024.json"


def test_unknown_filename_does_not_apply_a_profile():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename="Independent ESG Report.pdf",
        page_count=60,
    )

    assert result is None


def test_duplicate_filename_matches_fail_explicitly(tmp_path):
    profile = {
        "report_id": "duplicate",
        "company_name": "Duplicate",
        "report_year": 2024,
        "pdf_file": "Duplicate.pdf",
        "total_pdf_pages": 2,
        "page_numbering": {
            "report_index_pdf_page": 1,
            "report_index_report_page": 1,
        },
    }
    for name in ("one.json", "two.json"):
        (tmp_path / name).write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ReportProfileResolutionError) as exc_info:
        ReportProfileResolver(tmp_path).resolve(
            original_filename="duplicate.PDF",
            page_count=2,
        )

    assert exc_info.value.code == "duplicate_report_profile"


def test_missing_pdf_file_fails_profile_validation(tmp_path):
    (tmp_path / "invalid.json").write_text(
        json.dumps(
            {
                "report_id": "invalid",
                "company_name": "Invalid",
                "report_year": 2024,
                "total_pdf_pages": 2,
                "page_numbering": {
                    "report_index_pdf_page": 1,
                    "report_index_report_page": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReportProfileResolutionError) as exc_info:
        ReportProfileResolver(tmp_path).resolve(
            original_filename="Independent ESG Report.pdf",
            page_count=2,
        )

    assert exc_info.value.code == "invalid_report_profile"


def test_matching_profile_with_wrong_page_count_fails_explicitly(tmp_path):
    (tmp_path / "profile.json").write_text(
        json.dumps(
            {
                "report_id": "page-mismatch",
                "company_name": "Mismatch",
                "report_year": 2024,
                "pdf_file": "Mismatch.pdf",
                "total_pdf_pages": 10,
                "page_numbering": {
                    "report_index_pdf_page": 1,
                    "report_index_report_page": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReportProfileResolutionError) as exc_info:
        ReportProfileResolver(tmp_path).resolve(
            original_filename="Mismatch.pdf",
            page_count=9,
        )

    assert exc_info.value.code == "report_profile_page_count_mismatch"
