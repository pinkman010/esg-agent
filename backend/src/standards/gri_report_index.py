import re
from dataclasses import dataclass
from typing import Any

from src.domain.models import PageExtraction


@dataclass(frozen=True)
class GRIReportIndexEntry:
    disclosure_id: str
    candidate_pages: list[int]
    index_page: int
    report_index_pdf_page: int
    report_index_report_page: int
    source: str = "gri_report_index"

    def to_report_page(self, pdf_page: int) -> int:
        return pdf_page - (self.report_index_pdf_page - self.report_index_report_page)


def build_report_index(
    pages: list[PageExtraction],
    pack_items: list[dict[str, Any]],
) -> dict[str, GRIReportIndexEntry]:
    page_by_number = {page.page_number: page for page in pages}
    result: dict[str, GRIReportIndexEntry] = {}

    for item in pack_items:
        disclosure_id = str(item.get("canonical_disclosure_id") or "").strip()
        index_pdf_page = item.get("report_index_pdf_page")
        index_report_page = item.get("report_index_report_page")
        if not disclosure_id or not isinstance(index_pdf_page, int) or not isinstance(index_report_page, int):
            continue

        page = page_by_number.get(index_pdf_page)
        if page is None:
            continue

        row = _find_disclosure_row(disclosure_id, page.text)
        report_pages = _extract_report_pages_for_disclosure(disclosure_id, page.text)
        if not report_pages and not (row and (_is_no_information_restatement_row(row) or _is_omission_note_row(row))):
            continue

        offset = index_pdf_page - index_report_page
        source = "gri_report_index"
        if row and (_is_no_information_restatement_row(row) or _is_omission_note_row(row)):
            candidate_pages = [index_pdf_page]
            if _is_omission_note_row(row):
                source = "gri_report_index_omission_note"
        else:
            candidate_pages = sorted({report_page + offset for report_page in report_pages if report_page > 0})
        result[disclosure_id] = GRIReportIndexEntry(
            disclosure_id=disclosure_id,
            candidate_pages=candidate_pages,
            index_page=index_pdf_page,
            report_index_pdf_page=index_pdf_page,
            report_index_report_page=index_report_page,
            source=source,
        )

    return result


def _extract_report_pages_for_disclosure(disclosure_id: str, text: str) -> list[int]:
    row = _find_disclosure_row(disclosure_id, text)
    if row is None or _is_slash_only_row(row):
        return []
    return [int(value) for value in re.findall(r"(?<!\d)(\d{1,3})(?!\d)", row)]


def _find_disclosure_row(disclosure_id: str, text: str) -> str | None:
    pattern = re.compile(rf"(?<![\d-]){re.escape(disclosure_id)}(?![\d-])")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match is None:
            continue
        row_parts = [_before_next_index_token(line[match.end() :])]
        for next_line in lines[index + 1 :]:
            if _starts_next_index_row(next_line):
                break
            row_parts.append(_before_next_index_token(next_line))
        return " ".join(row_parts)
    return None


def _starts_next_index_row(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^(?:\d{1,3}-\d{1,3}|GRI\s+\d+)", stripped))


def _before_next_index_token(text: str) -> str:
    match = re.search(r"\s(?:\d{1,3}-\d{1,3}|GRI\s+\d+)\s", text)
    if match is None:
        return text
    return text[: match.start()]


def _is_slash_only_row(row: str) -> bool:
    return "/" in row and not re.search(r"(?<!\d)(\d{1,3})(?!\d)", row)


def _is_no_information_restatement_row(row: str) -> bool:
    return "无信息重述" in row


def _is_omission_note_row(row: str) -> bool:
    return "从略披露" in row
