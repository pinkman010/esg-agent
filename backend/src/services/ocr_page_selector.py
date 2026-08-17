from dataclasses import dataclass

from src.domain.enums import PageQualityFlag
from src.domain.models import PageExtraction
from src.reports.profile import ReportProfile
from src.services.ocr_errors import OcrError


@dataclass(frozen=True)
class OcrPageSelection:
    pages: tuple[int, ...]
    sources: tuple[tuple[int, str], ...]


class OcrPageSelectionError(OcrError):
    pass


def select_ocr_pages(
    *,
    explicit_pages: list[int] | None,
    parsed_pages: list[PageExtraction],
    report_profile: ReportProfile | None,
    page_count: int,
    max_pages: int,
) -> OcrPageSelection:
    if explicit_pages:
        selected = sorted(set(explicit_pages))
        _validate_page_range(selected, page_count)
        if len(selected) > max_pages:
            raise OcrPageSelectionError("ocr_page_limit_exceeded")
        return OcrPageSelection(
            pages=tuple(selected),
            sources=tuple((page_number, "explicit") for page_number in selected),
        )

    selections: list[tuple[int, str]] = []
    selected_pages: set[int] = set()

    if report_profile is not None:
        profile_pages = sorted(
            {
                assurance_page.pdf_page
                for assurance_page in report_profile.assurance_pages
                if assurance_page.requires_ocr
            }
        )
        _validate_page_range(profile_pages, page_count)
        for page_number in profile_pages:
            _append_selection(
                selections,
                selected_pages,
                page_number,
                "profile_requires_ocr",
                max_pages,
            )

    quality_flags = {
        PageQualityFlag.LOW_TEXT_DENSITY,
        PageQualityFlag.SCANNED,
    }
    quality_pages = sorted(
        {
            parsed_page.page_number
            for parsed_page in parsed_pages
            if quality_flags.intersection(parsed_page.quality_flags)
        }
    )
    _validate_page_range(quality_pages, page_count)
    for page_number in quality_pages:
        _append_selection(
            selections,
            selected_pages,
            page_number,
            "page_quality",
            max_pages,
        )

    return OcrPageSelection(
        pages=tuple(page_number for page_number, _source in selections),
        sources=tuple(selections),
    )


def _validate_page_range(pages: list[int], page_count: int) -> None:
    if any(page_number < 1 or page_number > page_count for page_number in pages):
        raise OcrPageSelectionError("ocr_page_out_of_range")


def _append_selection(
    selections: list[tuple[int, str]],
    selected_pages: set[int],
    page_number: int,
    source: str,
    max_pages: int,
) -> None:
    if page_number in selected_pages or len(selections) >= max_pages:
        return
    selections.append((page_number, source))
    selected_pages.add(page_number)
