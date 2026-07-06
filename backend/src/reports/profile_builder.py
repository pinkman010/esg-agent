from src.domain.models import PageExtraction
from src.reports.profile import IndexNotePageProfile, PageNumbering, ReportProfile


def build_initial_profile(
    report_id: str,
    company_name: str,
    report_year: int,
    pdf_file: str,
    total_pdf_pages: int,
    pages: list[PageExtraction],
    report_index_pdf_page: int,
    report_index_report_page: int,
) -> ReportProfile:
    index_pages = [
        page.page_number
        for page in pages
        if "GRI" in page.text and ("披露项" in page.text or "从略披露" in page.text or "信息重述" in page.text)
    ]
    page_numbering = PageNumbering(
        report_index_pdf_page=report_index_pdf_page,
        report_index_report_page=report_index_report_page,
    )
    return ReportProfile(
        report_id=report_id,
        company_name=company_name,
        report_year=report_year,
        pdf_file=pdf_file,
        total_pdf_pages=total_pdf_pages,
        page_numbering=page_numbering,
        gri_index={"pdf_pages": sorted(set(index_pages))},
        index_note_pages=_index_note_pages(pages, page_numbering),
    )


def _index_note_pages(pages: list[PageExtraction], page_numbering: PageNumbering) -> list[IndexNotePageProfile]:
    note_pages: list[IndexNotePageProfile] = []
    for page in pages:
        note_types: list[str] = []
        if "从略披露" in page.text:
            note_types.append("omission_note")
        if "信息重述" in page.text or "未发生违法违规事件" in page.text:
            note_types.append("index_statement")
        if not note_types:
            continue
        note_pages.append(
            IndexNotePageProfile(
                pdf_page=page.page_number,
                report_page=page.page_number - page_numbering.offset,
                note_types=note_types,
            )
        )
    return note_pages
