from src.domain.models import PageExtraction
from src.standards.gri_report_index import build_report_index


def test_build_report_index_extracts_candidate_pdf_pages_from_index_text():
    pages = [
        PageExtraction(
            report_id="report-1",
            page_number=71,
            text=(
                "GRI标准 披露项 章节索引 页码/备注\n"
                "2-1 组织详细情况 关于远景能源 5\n"
                "2-2 纳入组织可持续发展报告的实体 关于本报告 2\n"
                "2-5 外部鉴证 附录三：鉴证报告 76\n"
            ),
        )
    ]
    pack_items = [
        {
            "canonical_disclosure_id": "2-1",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        },
        {
            "canonical_disclosure_id": "2-2",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        },
        {
            "canonical_disclosure_id": "2-5",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        },
    ]

    index = build_report_index(pages, pack_items)

    assert index["2-1"].candidate_pages == [6]
    assert index["2-2"].candidate_pages == [3]
    assert index["2-5"].candidate_pages == [77]
    assert index["2-1"].index_page == 71


def test_build_report_index_ignores_not_disclosed_slash_only_rows():
    pages = [
        PageExtraction(
            report_id="report-1",
            page_number=71,
            text="2-4 信息重述 无信息重述 /\n2-5 外部鉴证 附录三：鉴证报告 76",
        )
    ]
    pack_items = [
        {
            "canonical_disclosure_id": "2-4",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        }
    ]

    index = build_report_index(pages, pack_items)

    assert "2-4" not in index


def test_build_report_index_stops_before_same_line_next_disclosure():
    pages = [
        PageExtraction(
            report_id="report-1",
            page_number=71,
            text="2-2 纳入组织可持续发展报告的实体 关于本报告 2 2-11 最高管治机构的主席 ESG 治理架构 12",
        )
    ]
    pack_items = [
        {
            "canonical_disclosure_id": "2-2",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        }
    ]

    index = build_report_index(pages, pack_items)

    assert index["2-2"].candidate_pages == [3]
