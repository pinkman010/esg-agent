from src.domain.models import DisclosureRequirement, PageExtraction
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


def test_profile_builder_detects_gri_index_heading_variants():
    pages = [
        PageExtraction(
            report_id="r1",
            page_number=50,
            text="GRI指标、联合国可持续发展目标（SDGs）索引 指标编号和描述 页码",
        ),
    ]

    profile = build_initial_profile(
        report_id="sample",
        company_name="Sample",
        report_year=2024,
        pdf_file="sample.pdf",
        total_pdf_pages=52,
        pages=pages,
        report_index_pdf_page=50,
        report_index_report_page=96,
    )

    assert profile.gri_index["pdf_pages"] == [50]


def test_profile_builder_extracts_goldwind_two_up_index_routes():
    pages = [
        PageExtraction(
            report_id="r1",
            page_number=50,
            text=(
                "GRI指标、联合国可持续发展目标（SDGs）索引 指标编号和描述 页码 "
                "305-2 能源间接（范畴2）温室气体排放 P46 "
                "414-1 使用社会标准筛选的新供应商 P59-P60 "
                "405-1 管治机构与员工的多元化 P34, P64, P77 "
                "GRI 205：反腐败 2016 205-2 反腐败政策和程序的传达及培训 P38 "
                "2-5 外部鉴证 P91-P92"
            ),
        ),
        PageExtraction(report_id="r1", page_number=47, text="第三方审验声明 AA1000AS v3"),
    ]
    requirements = [
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 305-2",
            requirement_id="GRI 305-2-a",
            requirement_text="Scope 2",
            keywords=["范围二"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 414-1",
            requirement_id="GRI 414-1-a",
            requirement_text="supplier screening",
            keywords=["供应商"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 405-1",
            requirement_id="GRI 405-1-a",
            requirement_text="diversity",
            keywords=["多元化"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 205-2",
            requirement_id="GRI 205-2-b",
            requirement_text="anti-corruption communication and training",
            keywords=["反腐败", "培训"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 2-5",
            requirement_id="GRI 2-5-b-ii",
            requirement_text="assurance",
            keywords=["审验"],
        ),
    ]

    profile = build_initial_profile(
        report_id="goldwind_2024",
        company_name="Goldwind",
        report_year=2024,
        pdf_file="goldwind.pdf",
        total_pdf_pages=52,
        pages=pages,
        report_index_pdf_page=50,
        report_index_report_page=96,
        requirements=requirements,
    )

    assert profile.requirement_routes["GRI 305-2-a"].candidate_pdf_pages == [25]
    assert profile.requirement_routes["GRI 414-1-a"].candidate_pdf_pages == [31, 32]
    assert profile.requirement_routes["GRI 405-1-a"].candidate_pdf_pages == [19, 34, 40]
    assert profile.requirement_routes["GRI 205-2-b"].candidate_pdf_pages == [21]
    assert profile.requirement_routes["GRI 2-5-b-ii"].candidate_pdf_pages == [47, 48]
    assert profile.assurance_pages[0].pdf_page == 47


def test_profile_builder_extracts_goldwind_index_routes_for_adjacent_disclosures():
    pages = [
        PageExtraction(
            report_id="goldwind",
            page_number=50,
            text=(
                "GRI指标、联合国可持续发展目标（SDGs）索引 指标编号和描述 页码 "
                "2-6 活动、价值链和其他业务关系 P08-P09, P58-P61 GRI 205：反腐败 2016 "
                "2-8 员工之外的工作者 P58-P61 SDG8 205-2 反腐败政策和程序的传达及培训 P38 "
                "管治 205-3 经确认的腐败事件和采取的行动 P38 "
                "GRI 414：供应商社会评估 2016 414-1 使用社会标准筛选的新供应商 P59-P60 "
                "GRI 305：排放 2016 305-1 直接（范畴1）温室气体排放 P46 "
                "305-2 能源间接（范畴2）温室气体排放 P46"
            ),
        ),
    ]
    requirements = [
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 205-2",
            requirement_id="GRI 205-2-b",
            requirement_text="anti-corruption training",
            keywords=["反腐败", "培训"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 205-3",
            requirement_id="GRI 205-3-a",
            requirement_text="confirmed incidents of corruption",
            keywords=["腐败事件"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 414-2",
            requirement_id="GRI 414-2-a",
            requirement_text="suppliers assessed for social impacts",
            keywords=["供应商", "社会影响"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 305-1",
            requirement_id="GRI 305-1-a",
            requirement_text="scope 1 emissions",
            keywords=["范围一"],
        ),
    ]

    profile = build_initial_profile(
        report_id="goldwind_2024",
        company_name="Goldwind",
        report_year=2024,
        pdf_file="goldwind.pdf",
        total_pdf_pages=52,
        pages=pages,
        report_index_pdf_page=50,
        report_index_report_page=96,
        requirements=requirements,
    )

    assert profile.requirement_routes["GRI 205-2-b"].candidate_pdf_pages == [21]
    assert profile.requirement_routes["GRI 205-3-a"].candidate_pdf_pages == [21]
    assert profile.requirement_routes["GRI 414-2-a"].candidate_pdf_pages == [31, 32]
    assert profile.requirement_routes["GRI 305-1-a"].candidate_pdf_pages == [25]
