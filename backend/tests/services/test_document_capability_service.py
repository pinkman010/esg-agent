from src.domain.enums import PageQualityFlag
from src.domain.models import PageExtraction
from src.services.document_capability_service import (
    DocumentCapabilityStatus,
    assess_document_capability,
)


def _page(
    page_number: int,
    *,
    text: str = "",
    flags: list[PageQualityFlag] | None = None,
) -> PageExtraction:
    return PageExtraction(
        report_id="report-1",
        page_number=page_number,
        text=text,
        quality_flags=flags or [],
    )


def test_digital_text_document_is_supported():
    result = assess_document_capability(
        [_page(1, text="A complete ESG disclosure.", flags=[PageQualityFlag.DIGITAL_TEXT])]
    )

    assert result.status is DocumentCapabilityStatus.SUPPORTED
    assert result.digital_text_page_count == 1
    assert result.scanned_page_count == 0


def test_mixed_digital_and_scanned_document_requires_review():
    result = assess_document_capability(
        [
            _page(1, text="A complete ESG disclosure.", flags=[PageQualityFlag.DIGITAL_TEXT]),
            _page(2, flags=[PageQualityFlag.LOW_TEXT_DENSITY, PageQualityFlag.SCANNED]),
        ]
    )

    assert result.status is DocumentCapabilityStatus.SUPPORTED_WITH_REVIEW
    assert result.digital_text_page_count == 1
    assert result.scanned_page_count == 1


def test_fully_scanned_document_is_explicitly_unsupported():
    result = assess_document_capability(
        [
            _page(1, flags=[PageQualityFlag.LOW_TEXT_DENSITY, PageQualityFlag.SCANNED]),
            _page(2, flags=[PageQualityFlag.LOW_TEXT_DENSITY, PageQualityFlag.SCANNED]),
        ]
    )

    assert result.status is DocumentCapabilityStatus.UNSUPPORTED_SCANNED_PDF
    assert result.digital_text_page_count == 0
    assert result.scanned_page_count == 2


def test_low_text_without_scan_evidence_is_not_misclassified_as_scanned():
    result = assess_document_capability(
        [_page(1, text="封面", flags=[PageQualityFlag.LOW_TEXT_DENSITY])]
    )

    assert result.status is DocumentCapabilityStatus.SUPPORTED_WITH_REVIEW
    assert result.digital_text_page_count == 0
    assert result.scanned_page_count == 0
