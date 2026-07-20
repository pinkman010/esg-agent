import pytest

from src.standards.requirement_structure import (
    EvaluationRole,
    RequirementStructureDecision,
    StructureStatus,
    canonical_requirement_id,
    compile_requirement_structure,
)


def test_parent_container_becomes_context_only():
    decision = RequirementStructureDecision(
        requirement_id="GRI 2-2-c",
        issue_code="parent_container_as_leaf",
        parent_requirement_id=None,
        source_note="父级/容器条款",
    )

    assert decision.evaluation_role is EvaluationRole.CONTEXT_ONLY


def test_child_inherits_parent_scope_and_remains_independent():
    compiled = compile_requirement_structure(
        items=[
            {
                "requirement_id": "GRI 2-2-c",
                "requirement_text": "if multiple entities, explain the consolidation approach:",
            },
            {
                "requirement_id": "GRI 2-2-c-i",
                "requirement_text": "adjustments for minority interests;",
            },
        ],
        decisions=[
            RequirementStructureDecision(
                requirement_id="GRI 2-2-c-i",
                issue_code="missing_parent_context",
                parent_requirement_id="GRI 2-2-c",
                source_note="缺少父级引导语",
            )
        ],
    )

    child = next(item for item in compiled if item["requirement_id"] == "GRI 2-2-c-i")
    assert child["evaluation_role"] == EvaluationRole.INDEPENDENT
    assert child["structure_status"] == StructureStatus.NORMALIZED
    assert child["context_requirement_ids"] == ["GRI 2-2-c"]
    assert child["effective_requirement_text"] == (
        "if multiple entities, explain the consolidation approach: "
        "adjustments for minority interests;"
    )


def test_merge_split_error_remains_method_pending():
    decision = RequirementStructureDecision(
        requirement_id="GRI TEST",
        issue_code="merge_split_error",
        parent_requirement_id=None,
        source_note="合并提取或拆分错误",
    )

    assert decision.evaluation_role is EvaluationRole.METHOD_PENDING


def test_canonical_requirement_id_maps_internal_checklist_id():
    assert canonical_requirement_id("current_gap:GRI2:2-2:c:i", "2-2") == "GRI 2-2-c-i"


@pytest.mark.parametrize(
    ("items", "decisions", "error"),
    [
        (
            [
                {"requirement_id": "GRI A", "requirement_text": "alpha"},
                {"requirement_id": "GRI A", "requirement_text": "duplicate"},
            ],
            [],
            "duplicate requirement_id",
        ),
        (
            [{"requirement_id": "GRI A", "requirement_text": ""}],
            [],
            "empty requirement_text",
        ),
        (
            [{"requirement_id": "GRI CHILD", "requirement_text": "child"}],
            [
                RequirementStructureDecision(
                    requirement_id="GRI CHILD",
                    issue_code="missing_parent_context",
                    parent_requirement_id="GRI MISSING",
                    source_note="missing parent",
                )
            ],
            "missing parent requirement",
        ),
        (
            [
                {"requirement_id": "GRI A", "requirement_text": "alpha"},
                {"requirement_id": "GRI B", "requirement_text": "beta"},
            ],
            [
                RequirementStructureDecision(
                    requirement_id="GRI A",
                    issue_code="missing_parent_context",
                    parent_requirement_id="GRI B",
                    source_note="cycle a",
                ),
                RequirementStructureDecision(
                    requirement_id="GRI B",
                    issue_code="missing_parent_context",
                    parent_requirement_id="GRI A",
                    source_note="cycle b",
                ),
            ],
            "parent cycle",
        ),
    ],
)
def test_structure_compiler_rejects_invalid_graph(items, decisions, error):
    with pytest.raises(ValueError, match=error):
        compile_requirement_structure(items=items, decisions=decisions)
