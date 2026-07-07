from src.domain.enums import EvidenceSourceMethod, PageQualityFlag
from src.domain.models import DocumentChunk
from src.tools.kpi_row_matcher import match_kpi_rows


def test_match_kpi_row_extracts_metric_value_and_unit():
    chunk = DocumentChunk(
        chunk_id="chunk-63",
        report_id="report-1",
        source_page=63,
        source_file_hash="file-hash",
        text="环境绩效 指标 单位 2024 能源使用总量 kWh 177,478,406.50 绿色电力 kWh 1,000",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["能源使用总量"], year_columns=["2024"])

    assert len(matches) == 1
    assert matches[0].row_label == "能源使用总量"
    assert matches[0].unit == "kWh"
    assert matches[0].value == "177,478,406.50"
    assert matches[0].source_page == 63


def test_kpi_row_matcher_extracts_goldwind_year_value_unit():
    chunk = DocumentChunk(
        chunk_id="goldwind-p47",
        report_id="goldwind",
        text="指标 单位 2024年 2023年 2022年\n职业病发病次数 次 0 0 0\n重大安全事故 次 0 0 0",
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["职业病发病次数"], year_columns=["2024年", "2024"])

    assert len(matches) == 1
    assert matches[0].row_label == "职业病发病次数"
    assert matches[0].unit == "次"
    assert matches[0].value == "0"
    assert matches[0].year_column == "2024年"
    assert matches[0].preview.startswith("职业病发病次数")


def test_kpi_row_matcher_matches_terms_without_exact_spacing():
    chunk = DocumentChunk(
        chunk_id="goldwind-p47",
        report_id="goldwind",
        text=(
            "指标 单位 2024年 2023年 2022年 "
            "员工可记录工伤事故率 次/百万工时 0.18 0.20 0.25 "
            "员工因工死亡人数 人 0 0 0 "
            "员工总工时 小时 87654321 81234567 79876543"
        ),
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows(
        [chunk],
        ["员工因工死亡人数", "员工总工时"],
        year_columns=["2024年", "2024"],
    )

    assert [match.row_label for match in matches] == ["员工因工死亡人数", "员工总工时"]
    assert matches[0].unit == "人"
    assert matches[0].value == "0"
    assert matches[1].unit == "小时"
    assert matches[1].value == "87654321"


def test_kpi_row_matcher_does_not_match_metric_when_no_numeric_value_nearby():
    chunk = DocumentChunk(
        chunk_id="goldwind-p47",
        report_id="goldwind",
        text="员工因工死亡人数 说明文字 无数据 员工总工时 小时 87654321",
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["员工因工死亡人数"], year_columns=["2024年", "2024"])

    assert matches == []


def test_match_kpi_row_does_not_match_unrelated_metric():
    chunk = DocumentChunk(
        chunk_id="chunk-67",
        report_id="report-1",
        source_page=67,
        source_file_hash="file-hash",
        text="供应商绩效 指标 单位 2024 使用环境评价维度筛选的新供应商百分比 % 100",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["使用社会评价维度筛选的新供应商百分比"], year_columns=["2024"])

    assert matches == []
