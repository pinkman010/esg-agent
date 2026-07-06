from src.domain.models import PageExtraction
from src.reports.profile_builder import build_initial_profile


def test_profile_builder_uses_gri_index_and_page_offset():
    pages = [
        PageExtraction(report_id="r1", page_number=71, text="GRI 2-4 信息重述 无信息重述 70"),
        PageExtraction(report_id="r1", page_number=72, text="GRI 204-1 向当地供应商采购的支出比例 因商业保密限制从略披露"),
    ]

    profile = build_initial_profile(
        report_id="sample",
        company_name="Sample",
        report_year=2024,
        pdf_file="sample.pdf",
        total_pdf_pages=78,
        pages=pages,
        report_index_pdf_page=71,
        report_index_report_page=70,
    )

    assert profile.report_page_for_pdf_page(72) == 71
    assert profile.gri_index["pdf_pages"] == [71, 72]


def test_profile_builder_marks_index_note_pages():
    pages = [
        PageExtraction(report_id="r1", page_number=71, text="GRI 2-4 信息重述 无信息重述 70"),
        PageExtraction(report_id="r1", page_number=73, text="GRI 207-4 国别报告 因商业保密限制从略披露"),
    ]

    profile = build_initial_profile(
        report_id="sample",
        company_name="Sample",
        report_year=2024,
        pdf_file="sample.pdf",
        total_pdf_pages=78,
        pages=pages,
        report_index_pdf_page=71,
        report_index_report_page=70,
    )

    note_pages = {page.pdf_page: page for page in profile.index_note_pages}
    assert note_pages[71].note_types == ["index_statement"]
    assert note_pages[73].note_types == ["omission_note"]
