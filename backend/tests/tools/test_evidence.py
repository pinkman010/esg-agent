from src.domain.enums import EvidenceSourceMethod
from src.domain.models import DisclosureTask, DocumentChunk
from src.tools.evidence import build_evidence_preview, build_kpi_evidence_preview, chunk_to_evidence


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


def test_build_evidence_preview_prefers_anti_corruption_audit_strategy_anchor():
    text = (
        "公司设有举报渠道和信息安全管理机制。"
        "审计委员会领导审计监察部开展反腐败制度建设，"
        "并根据不同业务单位的业务特点、重要性、风险程度制定审计策略，"
        "在审计中重点关注商业道德问题。"
        "报告期内，公司开展反舞弊培训。"
    )

    preview = build_evidence_preview(text, ["业务单位", "风险程度", "审计策略", "商业道德问题"])

    assert "业务单位" in preview
    assert "风险程度" in preview
    assert "审计策略" in preview
    assert "商业道德问题" in preview


def test_chunk_to_evidence_preview_prefers_kpi_row_preview():
    task = DisclosureTask(
        task_id="task",
        run_id="run",
        report_id="goldwind",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 403-9",
        requirement_id="GRI 403-9-a-i",
        requirement_text="fatalities",
        keywords=["死亡", "工伤"],
    )
    chunk = DocumentChunk(
        chunk_id="chunk",
        report_id="goldwind",
        text="页眉 目录 相邻表格 职业病发病次数 次 0 0 0",
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
    )

    evidence = chunk_to_evidence(
        task,
        chunk,
        retrieval_metadata={"kpi_row_preview": "职业病发病次数 次 0"},
    )

    assert evidence.evidence_preview == "职业病发病次数 次 0"


def test_chunk_to_evidence_ignores_blank_kpi_row_preview():
    task = DisclosureTask(
        task_id="task",
        run_id="run",
        report_id="goldwind",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 418-1",
        requirement_id="GRI 418-1-a",
        requirement_text="customer privacy complaints",
        keywords=["客户隐私", "投诉"],
    )
    chunk = DocumentChunk(
        chunk_id="chunk",
        report_id="goldwind",
        text="页眉 目录 2024年公司未接到任何涉及侵犯客户隐私或数据丢失的投诉。",
        source_page=61,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
    )

    evidence = chunk_to_evidence(task, chunk, retrieval_metadata={"kpi_row_preview": "   "})

    assert "客户隐私" in evidence.evidence_preview
    assert evidence.evidence_preview != "   "
