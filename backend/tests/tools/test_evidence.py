from src.tools.evidence import build_kpi_evidence_preview


def test_build_kpi_evidence_preview_prefers_target_metric_row():
    text = (
        "总耗水量(t) 277,323.60 177,280.10 69,292.00 "
        "范围一(tCO2e) 4,728.96 4,251.21 3,757.00 "
        "范围二 - 基于市场(tCO2e) 2,359.23 2,114.54 883.00 "
        "污染物排放总量 "
        "范围二 - 基于位置(tCO2e) 57,897.05 42,929.76 19,524.00 "
        "化学需氧量(kg) 11,973.00 31,053.57 20,558.83"
    )

    preview = build_kpi_evidence_preview(text, ["范围二 - 基于位置"])

    assert "范围二 - 基于位置(tCO2e) 57,897.05" in preview
    assert "总耗水量" not in preview
