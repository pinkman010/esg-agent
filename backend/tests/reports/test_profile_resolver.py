import json
from pathlib import Path

import pytest

from src.reports.profile_resolver import (
    ReportProfileResolutionError,
    ReportProfileResolver,
)


PROFILE_ROOT = Path("data/reports/profiles")
ENVISION_SHA256 = (
    "57360dcda8e6256726be5d2a49f8921e13187b40ae44661549903f702df38068"
)
GOLDWIND_SHA256 = (
    "f712694a6c05c599f3a272f314aa749be393f9007d92bc1fa6fd11bac5ad0119"
)


def test_resolves_envision_profile_from_declared_filename():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename="Envision Energy 2024-zh.pdf",
        page_count=78,
        source_file_hash=ENVISION_SHA256,
    )

    assert result == PROFILE_ROOT / "envision_2024.json"


def test_resolves_goldwind_profile_from_declared_filename():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename="Goldwind 2024-zh.pdf",
        page_count=52,
        source_file_hash=GOLDWIND_SHA256,
    )

    assert result == PROFILE_ROOT / "goldwind_2024.json"


def test_filename_matching_normalizes_case_unicode_whitespace_and_path():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename=" uploads/  ＧＯＬＤＷＩＮＤ 2024-ZH.PDF  ",
        page_count=52,
        source_file_hash=GOLDWIND_SHA256.upper(),
    )

    assert result == PROFILE_ROOT / "goldwind_2024.json"


def test_unknown_filename_does_not_apply_a_profile():
    result = ReportProfileResolver(PROFILE_ROOT).resolve(
        original_filename="Independent ESG Report.pdf",
        page_count=60,
        source_file_hash="a" * 64,
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
            source_file_hash="a" * 64,
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
            source_file_hash="a" * 64,
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
            source_file_hash="a" * 64,
        )

    assert exc_info.value.code == "report_profile_page_count_mismatch"


def test_matching_profile_with_wrong_source_hash_fails_explicitly():
    with pytest.raises(ReportProfileResolutionError) as exc_info:
        ReportProfileResolver(PROFILE_ROOT).resolve(
            original_filename="Goldwind 2024-zh.pdf",
            page_count=52,
            source_file_hash="0" * 64,
        )

    assert exc_info.value.code == "report_profile_source_hash_mismatch"


def test_matching_profile_without_source_hash_fails_explicitly(tmp_path):
    (tmp_path / "profile.json").write_text(
        json.dumps(
            {
                "report_id": "hash-missing",
                "company_name": "Missing Hash",
                "report_year": 2024,
                "pdf_file": "Missing Hash.pdf",
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
            original_filename="Missing Hash.pdf",
            page_count=2,
            source_file_hash="a" * 64,
        )

    assert exc_info.value.code == "report_profile_source_hash_missing"
