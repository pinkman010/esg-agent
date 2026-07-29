from dataclasses import dataclass
from enum import StrEnum

from src.domain.enums import PageQualityFlag
from src.domain.models import PageExtraction


class DocumentCapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    SUPPORTED_WITH_REVIEW = "supported_with_review"
    UNSUPPORTED_SCANNED_PDF = "unsupported_scanned_pdf"


@dataclass(frozen=True)
class DocumentCapabilityResult:
    status: DocumentCapabilityStatus
    page_count: int
    digital_text_page_count: int
    scanned_page_count: int
    low_text_density_page_count: int


class UnsupportedScannedPdfError(ValueError):
    code = DocumentCapabilityStatus.UNSUPPORTED_SCANNED_PDF.value
    user_message = "当前版本无法分析全扫描 PDF，请改用可检索文本 PDF。"

    def __init__(self) -> None:
        super().__init__(self.user_message)


def assess_document_capability(
    pages: list[PageExtraction],
) -> DocumentCapabilityResult:
    digital_text_page_count = 0
    scanned_page_count = 0
    low_text_density_page_count = 0

    for page in pages:
        flags = set(page.quality_flags)
        if PageQualityFlag.SCANNED in flags:
            scanned_page_count += 1
        if PageQualityFlag.LOW_TEXT_DENSITY in flags:
            low_text_density_page_count += 1
        if PageQualityFlag.DIGITAL_TEXT in flags or (
            not flags and bool(page.text.strip())
        ):
            digital_text_page_count += 1

    page_count = len(pages)
    fully_scanned = (
        page_count > 0
        and scanned_page_count == page_count
        and digital_text_page_count == 0
    )
    has_quality_review_signal = (
        page_count == 0
        or scanned_page_count > 0
        or low_text_density_page_count > 0
    )
    if fully_scanned:
        status = DocumentCapabilityStatus.UNSUPPORTED_SCANNED_PDF
    elif has_quality_review_signal:
        status = DocumentCapabilityStatus.SUPPORTED_WITH_REVIEW
    else:
        status = DocumentCapabilityStatus.SUPPORTED

    return DocumentCapabilityResult(
        status=status,
        page_count=page_count,
        digital_text_page_count=digital_text_page_count,
        scanned_page_count=scanned_page_count,
        low_text_density_page_count=low_text_density_page_count,
    )
