import pytest

from src.domain.enums import PageQualityFlag
from src.domain.models import PageExtraction
from src.reports.profile import AssurancePageProfile, PageNumbering, ReportProfile
from src.services.ocr_page_selector import OcrPageSelectionError, select_ocr_pages


def page(page_number: int, *quality_flags: PageQualityFlag) -> PageExtraction:
    return PageExtraction(
        report_id="report-1",
        page_number=page_number,
        quality_flags=list(quality_flags),
    )


def profile_with_required_ocr_page(page_number: int) -> ReportProfile:
    return ReportProfile(
        report_id="report-1",
        company_name="测试公司",
        report_year=2024,
        pdf_file="report.pdf",
        total_pdf_pages=78,
        page_numbering=PageNumbering(
            report_index_pdf_page=1,
            report_index_report_page=1,
            total_pdf_pages=78,
        ),
        assurance_pages=[
            AssurancePageProfile(pdf_page=page_number, requires_ocr=True),
        ],
    )


def test_explicit_pages_override_profile_and_quality_pages():
    selection = select_ocr_pages(
        explicit_pages=[77, 77],
        parsed_pages=[
            page(
                78,
                PageQualityFlag.LOW_TEXT_DENSITY,
                PageQualityFlag.SCANNED,
            )
        ],
        report_profile=profile_with_required_ocr_page(77),
        page_count=78,
        max_pages=5,
    )

    assert selection.pages == (77,)
    assert selection.sources == ((77, "explicit"),)


def test_automatic_selection_prioritizes_profile_then_page_quality():
    selection = select_ocr_pages(
        explicit_pages=[],
        parsed_pages=[
            page(
                78,
                PageQualityFlag.LOW_TEXT_DENSITY,
                PageQualityFlag.SCANNED,
            )
        ],
        report_profile=profile_with_required_ocr_page(77),
        page_count=78,
        max_pages=5,
    )

    assert selection.pages == (77, 78)
    assert selection.sources == (
        (77, "profile_requires_ocr"),
        (78, "page_quality"),
    )


def test_automatic_selection_deduplicates_and_respects_page_budget():
    selection = select_ocr_pages(
        explicit_pages=None,
        parsed_pages=[
            page(2, PageQualityFlag.LOW_TEXT_DENSITY),
            page(3, PageQualityFlag.SCANNED),
        ],
        report_profile=profile_with_required_ocr_page(2),
        page_count=3,
        max_pages=2,
    )

    assert selection.pages == (2, 3)
    assert selection.sources == (
        (2, "profile_requires_ocr"),
        (3, "page_quality"),
    )


def test_automatic_selection_returns_empty_when_no_page_requires_ocr():
    selection = select_ocr_pages(
        explicit_pages=None,
        parsed_pages=[page(1, PageQualityFlag.DIGITAL_TEXT)],
        report_profile=None,
        page_count=1,
        max_pages=5,
    )

    assert selection.pages == ()
    assert selection.sources == ()


@pytest.mark.parametrize("pages", [[0], [-1], [79]])
def test_explicit_page_out_of_range_is_rejected(pages):
    with pytest.raises(OcrPageSelectionError) as exc_info:
        select_ocr_pages(
            explicit_pages=pages,
            parsed_pages=[],
            report_profile=None,
            page_count=78,
            max_pages=5,
        )

    assert exc_info.value.code == "ocr_page_out_of_range"


def test_explicit_page_limit_is_rejected():
    with pytest.raises(OcrPageSelectionError) as exc_info:
        select_ocr_pages(
            explicit_pages=[1, 2, 3, 4, 5, 6],
            parsed_pages=[],
            report_profile=None,
            page_count=78,
            max_pages=5,
        )

    assert exc_info.value.code == "ocr_page_limit_exceeded"
