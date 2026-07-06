from pathlib import Path

from src.reports.profile import load_report_profile


def test_load_envision_2024_profile_maps_pdf_and_report_pages():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    assert profile.report_id == "envision_2024"
    assert profile.pdf_file == "Envision Energy 2024-zh.pdf"
    assert profile.report_page_for_pdf_page(63) == 62
    assert profile.pdf_page_for_report_page(62) == 63


def test_envision_2024_profile_declares_verified_kpi_pages():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    assert profile.kpi_pdf_pages == [63, 64, 65, 66, 67, 68]
    assert profile.is_kpi_page(67)
    assert not profile.is_kpi_page(62)


def test_profile_returns_requirement_route_without_global_logic():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    route = profile.route_for_requirement("GRI 414-1-a")

    assert route is not None
    assert route.candidate_pdf_pages == [67]
    assert route.kpi_table_pages == [67]


def test_envision_2024_profile_declares_verified_sections():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    sections = {section.name: section for section in profile.sections}

    assert sections["stakeholder_engagement"].pdf_pages == [14, 15]
    assert sections["ohs_management"].pdf_pages == [38, 39, 40, 41]
    assert "利益相关方" in sections["community_program"].terms


def test_envision_2024_profile_declares_index_note_pages():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    note_pages = {page.pdf_page: page for page in profile.index_note_pages}

    assert note_pages[72].report_page == 71
    assert "index_statement" in note_pages[72].note_types
    assert "omission_note" in note_pages[73].note_types
