from src.domain.enums import PageQualityFlag
from src.domain.models import DisclosureRequirement, PageExtraction
from src.reports.profile_builder import build_initial_profile, calibrate_requirement_routes


def test_profile_builder_detects_kpi_table_pages_and_routes_them_to_requirements():
    pages = [
        PageExtraction(
            report_id="goldwind",
            page_number=25,
            text="环境关键绩效 指标 单位 2024年 2023年 范围一温室气体排放量 tCO2e 123 120",
            table_count=1,
            quality_flags=[PageQualityFlag.COMPLEX_TABLE],
        ),
        PageExtraction(
            report_id="goldwind",
            page_number=50,
            text="GRI 内容索引 披露项 305-1 P46",
        ),
    ]
    requirements = [
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 305-1",
            requirement_id="GRI 305-1-a",
            requirement_text="gross direct Scope 1 GHG emissions",
            keywords=["范围一温室气体排放量"],
        )
    ]

    profile = build_initial_profile(
        report_id="goldwind",
        company_name="Goldwind",
        report_year=2024,
        pdf_file="goldwind.pdf",
        total_pdf_pages=52,
        pages=pages,
        report_index_pdf_page=50,
        report_index_report_page=96,
        requirements=requirements,
    )

    assert profile.kpi_pdf_pages == [25]
    assert profile.requirement_routes["GRI 305-1-a"].kpi_table_pages == [25]


def test_profile_calibration_applies_reviewed_pages_without_changing_metric_terms():
    profile = build_initial_profile(
        report_id="goldwind",
        company_name="Goldwind",
        report_year=2024,
        pdf_file="goldwind.pdf",
        total_pdf_pages=52,
        pages=[
            PageExtraction(
                report_id="goldwind",
                page_number=26,
                text="指标 单位 2024年 范围3 万吨二氧化碳当量 672.11",
            ),
            PageExtraction(report_id="goldwind", page_number=50, text="GRI 内容索引 披露项 305-3 P46"),
        ],
        report_index_pdf_page=50,
        report_index_report_page=96,
        requirements=[
            DisclosureRequirement(
                standard_id="GRI",
                standard_version="2021",
                disclosure_id="GRI 305-3",
                requirement_id="GRI 305-3-a",
                requirement_text="Scope 3 emissions",
                keywords=["范围3"],
            )
        ],
    )

    calibrated = calibrate_requirement_routes(profile, {"GRI 305-3-a": [26], "GRI 418-1-a": []})

    assert calibrated.requirement_routes["GRI 305-3-a"].candidate_pdf_pages == [26]
    assert calibrated.requirement_routes["GRI 305-3-a"].metric_terms == ["范围3"]
    assert calibrated.requirement_routes["GRI 418-1-a"].candidate_pdf_pages == []


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


def test_profile_builder_extracts_goldwind_section_ranges():
    pages = [
        PageExtraction(report_id="goldwind", page_number=8, text="02 可持续发展管理 战略规划"),
        PageExtraction(report_id="goldwind", page_number=15, text="产品服务与研发创新 产品质量与安全"),
        PageExtraction(report_id="goldwind", page_number=19, text="诚信合规经营 公司治理 风险合规管理"),
        PageExtraction(report_id="goldwind", page_number=25, text="绿色环保运营 碳减排与碳中和"),
        PageExtraction(report_id="goldwind", page_number=31, text="可持续产业链 供应链可持续"),
        PageExtraction(report_id="goldwind", page_number=38, text="公平健康工作环境 提升本质安全"),
        PageExtraction(report_id="goldwind", page_number=42, text="和谐社区关系 社区沟通与发展"),
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
    )

    sections = {section.name: section for section in profile.sections}
    assert sections["可持续发展管理"].pdf_pages == list(range(8, 15))
    assert sections["产品服务与研发创新"].pdf_pages == list(range(15, 19))
    assert sections["诚信合规经营"].pdf_pages == list(range(19, 25))
    assert sections["绿色环保运营"].pdf_pages == list(range(25, 31))
    assert sections["可持续产业链"].pdf_pages == list(range(31, 38))
    assert sections["公平健康工作环境"].pdf_pages == list(range(38, 42))
    assert sections["和谐社区关系"].pdf_pages == list(range(42, 47))


def test_profile_builder_expands_goldwind_topic_routes_to_missing_leaf_requirements():
    pages = [
        PageExtraction(
            report_id="goldwind",
            page_number=50,
            text=(
                "GRI指标、联合国可持续发展目标（SDGs）索引 指标编号和描述 页码 "
                "GRI 205：反腐败 2016 205-1 已进行腐败风险评估的运营点 P38 "
                "GRI 414：供应商社会评估 2016 414-1 使用社会标准筛选的新供应商 P59-P60"
            ),
        )
    ]
    requirements = [
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 205-1",
            requirement_id="GRI 205-1-a",
            requirement_text="operations assessed for risks related to corruption",
            keywords=["腐败", "风险评估"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 414-1",
            requirement_id="GRI 414-1-a",
            requirement_text="new suppliers screened using social criteria",
            keywords=["供应商", "社会标准", "筛选"],
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

    assert profile.requirement_routes["GRI 205-1-a"].candidate_pdf_pages == [21]
    assert profile.requirement_routes["GRI 414-1-a"].candidate_pdf_pages == [31, 32]
