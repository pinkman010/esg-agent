from src.standards.leaf_sufficiency import get_leaf_sufficiency_rule


def test_leaf_sufficiency_keeps_neighbor_requirements_out_of_missing_items() -> None:
    rules = {
        "GRI 306-3-a": ("回收", "处置"),
        "GRI 404-2-a": ("转型援助", "退休", "解雇"),
        "GRI 416-1-a": ("标签程序", "信息类别"),
        "GRI 406-1-b-i": ("补救计划",),
        "GRI 406-1-b-ii": ("实施结果", "结案"),
        "GRI 408-1-b": ("青年工人危险工作",),
    }

    for requirement_id, forbidden_terms in rules.items():
        rule = get_leaf_sufficiency_rule(requirement_id)
        assert rule is not None
        text = " ".join(rule.missing_item_templates)
        assert all(term not in text for term in forbidden_terms)


def test_leaf_sufficiency_defines_atomic_manual_reviewed_components() -> None:
    assert get_leaf_sufficiency_rule("GRI 305-2-d-i").missing_item_templates == ("基准年选择理由",)
    assert get_leaf_sufficiency_rule("GRI 406-1-b-i").missing_item_templates == ("歧视事件是否已由组织审查",)
    assert get_leaf_sufficiency_rule("GRI 406-1-b-ii").missing_item_templates == ("补救计划是否正在实施",)
    assert get_leaf_sufficiency_rule("GRI 305-2-e").missing_item_templates == ("GWP来源或引用",)


def test_leaf_sufficiency_has_no_report_specific_metadata() -> None:
    for requirement_id in (
        "GRI 303-1-a",
        "GRI 305-2-e",
        "GRI 306-3-a",
        "GRI 401-1-b",
        "GRI 404-2-a",
        "GRI 416-1-a",
        "GRI 306-1-a",
        "GRI 405-1-a",
        "GRI 407-1-b",
    ):
        rule = get_leaf_sufficiency_rule(requirement_id)
        assert rule is not None
        serialized = repr(rule)
        assert "pdf" not in serialized.lower()
        assert "goldwind" not in serialized.lower()
