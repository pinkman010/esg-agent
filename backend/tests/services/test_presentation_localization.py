import logging

from src.services.presentation_localization import (
    localize_missing_items,
    localize_rationale,
)


def test_localizes_confirmed_rationale_and_missing_item_templates():
    assert localize_rationale(
        "The report index contains an omission note, but no substantive disclosure evidence was found."
    ) == "报告 GRI 内容索引包含从略说明，但未找到实质性披露证据。"
    assert localize_missing_items(
        [
            "EVG&D source basis from audited financial/P&L statement or internally audited management accounts",
            "applicability of EVG&D source basis",
        ]
    ) == [
        "EVG&D 数据来源依据：经审计的财务报表或损益表，或经内部审计的管理账目",
        "EVG&D 数据来源依据的适用性说明",
    ]


def test_localizes_controlled_rationale_families_without_claiming_full_disclosure():
    assert localize_rationale(
        "Water evidence is directionally relevant, but the full GRI-required method remains subject to sufficiency review."
    ) == "现有证据与该要求相关，但尚未完整满足 GRI 披露要求，需人工复核证据充分性。"
    assert localize_rationale(
        "The report does not disclose average training hours by gender."
    ) == "报告未提供该要求所需的完整披露，具体缺失内容见“缺失项”。"
    assert localize_rationale(
        "Evidence directly satisfies the count requirement."
    ) == "已找到直接支持该要求的报告证据。"


def test_unknown_templates_remain_unchanged_and_emit_only_a_monitoring_fingerprint(caplog):
    value = "A newly introduced free-form audit statement."

    with caplog.at_level(logging.WARNING):
        result = localize_rationale(value)

    assert result == value
    assert "unmapped_presentation_template" in caplog.text
    assert value not in caplog.text


def test_exact_only_mode_preserves_human_free_text_and_chinese_input():
    human_text = "Reviewer says the source does not disclose this clearly."
    chinese_text = "人工复核认为证据范围仍需确认。"

    assert localize_rationale(human_text, exact_only=True) == human_text
    assert localize_rationale(chinese_text) == chinese_text


def test_localizes_mixed_guardrail_terms_used_by_current_577_dataset():
    assert localize_missing_items(
        [
            "exclude effluent unless national law requires inclusion in total waste",
            "完整 OHS 范围、覆盖、流程、职责或获取方式",
            "recovery operation 拆分",
            "GWP rates",
        ]
    ) == [
        "除非国家法律要求计入废弃物总量，否则排除废水",
        "完整的职业健康与安全范围、覆盖、流程、职责或获取方式",
        "按回收利用作业类型拆分",
        "GWP 数值",
    ]
