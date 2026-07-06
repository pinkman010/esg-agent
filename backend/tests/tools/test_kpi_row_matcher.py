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
