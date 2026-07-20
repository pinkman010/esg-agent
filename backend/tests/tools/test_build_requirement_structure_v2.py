import json
from hashlib import sha256

import pytest
from openpyxl import Workbook

from src.tools.build_requirement_structure_v2 import (
    build_requirement_structure_assets,
    read_structure_decisions,
)


def _write_review_workbook(path, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "人工复核577"
    sheet.append(["人工复核"])
    sheet.append([])
    sheet.append([])
    sheet.append(
        [
            "requirement_id",
            "standard_verified",
            "primary_issue_type",
            "review_note",
            "second_review_note",
        ]
    )
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_read_structure_decisions_uses_confirmed_review_notes_without_modifying_workbook(
    tmp_path,
):
    workbook_path = tmp_path / "review.xlsx"
    _write_review_workbook(
        workbook_path,
        [
            [
                "GRI 2-2-c",
                "no",
                None,
                "当前行是引出下级子要求的父级/容器条款。",
                "二次复核结论：同意退回。",
            ],
            [
                "GRI 2-2-c-i",
                "no",
                None,
                "当前子项依赖上级GRI 2-2-c的引导语/条件。",
                "二次复核结论：同意退回。",
            ],
            [
                "GRI 302-1-c",
                "no",
                None,
                "当前文本把四个并列叶子项合并在同一行，应重新拆分。",
                "当前行合并了多个并列要求。",
            ],
            ["GRI 2-1-a", "yes", None, "核对通过。", None],
        ],
    )
    original_hash = sha256(workbook_path.read_bytes()).hexdigest()

    decisions = read_structure_decisions(workbook_path)

    assert [item.issue_code for item in decisions] == [
        "parent_container_as_leaf",
        "missing_parent_context",
        "merge_split_error",
    ]
    assert decisions[1].parent_requirement_id == "GRI 2-2-c"
    assert sha256(workbook_path.read_bytes()).hexdigest() == original_hash


def test_read_structure_decisions_accepts_explicit_issue_code(tmp_path):
    workbook_path = tmp_path / "review.xlsx"
    _write_review_workbook(
        workbook_path,
        [
            [
                "GRI TEST",
                "no",
                "merge_split_error",
                "需拆分。",
                "二次复核确认。",
            ]
        ],
    )

    decisions = read_structure_decisions(workbook_path)

    assert decisions[0].issue_code == "merge_split_error"


def test_read_structure_decisions_rejects_unclassified_blocker(tmp_path):
    workbook_path = tmp_path / "review.xlsx"
    _write_review_workbook(
        workbook_path,
        [["GRI TEST", "no", None, "存在问题。", "同意。"]],
    )

    with pytest.raises(ValueError, match="cannot classify structure issue"):
        read_structure_decisions(workbook_path)


def _source_item(raw_id, parent_id, disclosure_id, text):
    return {
        "requirement_id": raw_id,
        "parent_requirement_id": parent_id,
        "canonical_disclosure_id": disclosure_id,
        "requirement_text": text,
        "requirement_type": "requirement",
        "is_mandatory": True,
        "scoring_role": "hard_score",
        "assessment_mode": "current_gap",
    }


def _write_source_checklist(path, *, child_parent="current_gap:GRI2:2-2:c"):
    document = {
        "metadata": {"manifest_version": "test-v1"},
        "requirements": [
            _source_item(
                "current_gap:GRI2:2-2:c",
                "current_gap:GRI2:2-2",
                "2-2",
                "if multiple entities, explain the consolidation approach:",
            ),
            _source_item(
                "current_gap:GRI2:2-2:c:i",
                child_parent,
                "2-2",
                "adjustments for minority interests;",
            ),
            _source_item(
                "current_gap:GRI302:302-1:c",
                "current_gap:GRI302:302-1",
                "302-1",
                "four merged energy consumption leaves",
            ),
            _source_item(
                "current_gap:GRI2:2-1:a",
                "current_gap:GRI2:2-1",
                "2-1",
                "report its legal name;",
            ),
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")


def _write_structure_review_workbook(path):
    _write_review_workbook(
        path,
        [
            [
                "GRI 2-2-c",
                "no",
                None,
                "当前行是引出下级子要求的父级/容器条款。",
                "二次复核结论：同意退回。",
            ],
            [
                "GRI 2-2-c-i",
                "no",
                None,
                "当前子项依赖上级GRI 2-2-c的引导语/条件。",
                "二次复核结论：同意退回。",
            ],
            [
                "GRI 302-1-c",
                "no",
                None,
                "当前文本把四个并列叶子项合并在同一行，应重新拆分。",
                "当前行合并了多个并列要求。",
            ],
            ["GRI 2-1-a", "yes", None, "核对通过。", None],
        ],
    )


def test_build_requirement_structure_assets_writes_versioned_documents(tmp_path):
    workbook_path = tmp_path / "review.xlsx"
    checklist_path = tmp_path / "checklist.json"
    structure_path = tmp_path / "structure-v2.json"
    compiled_path = tmp_path / "checklist-v2.json"
    _write_structure_review_workbook(workbook_path)
    _write_source_checklist(checklist_path)
    source_hash = sha256(checklist_path.read_bytes()).hexdigest()
    review_hash = sha256(workbook_path.read_bytes()).hexdigest()

    metadata = build_requirement_structure_assets(
        review_workbook=workbook_path,
        source_checklist=checklist_path,
        output_structure=structure_path,
        output_checklist=compiled_path,
        expected_review_sha256=review_hash,
        expected_counts={
            "standard_unit_count": 4,
            "verified_count": 1,
            "context_only_count": 1,
            "normalized_count": 1,
            "method_pending_count": 1,
            "independent_assessment_count": 2,
        },
    )

    assert metadata["manifest_version"] == "gri-requirement-structure-v2"
    assert metadata["source_review_sha256"] == review_hash
    assert sha256(checklist_path.read_bytes()).hexdigest() == source_hash
    compiled = json.loads(compiled_path.read_text(encoding="utf-8"))
    by_id = {item["requirement_id"]: item for item in compiled["requirements"]}
    child = by_id["current_gap:GRI2:2-2:c:i"]
    assert child["evaluation_role"] == "independent"
    assert child["context_requirement_ids"] == ["GRI 2-2-c"]
    assert child["effective_requirement_text"].endswith(
        "adjustments for minority interests;"
    )


def test_build_requirement_structure_assets_does_not_overwrite_on_count_mismatch(
    tmp_path,
):
    workbook_path = tmp_path / "review.xlsx"
    checklist_path = tmp_path / "checklist.json"
    structure_path = tmp_path / "structure-v2.json"
    compiled_path = tmp_path / "checklist-v2.json"
    _write_structure_review_workbook(workbook_path)
    _write_source_checklist(checklist_path)
    structure_path.write_text("old structure", encoding="utf-8")
    compiled_path.write_text("old checklist", encoding="utf-8")

    with pytest.raises(ValueError, match="structure count mismatch"):
        build_requirement_structure_assets(
            review_workbook=workbook_path,
            source_checklist=checklist_path,
            output_structure=structure_path,
            output_checklist=compiled_path,
            expected_review_sha256=sha256(workbook_path.read_bytes()).hexdigest(),
            expected_counts={"standard_unit_count": 577},
        )

    assert structure_path.read_text(encoding="utf-8") == "old structure"
    assert compiled_path.read_text(encoding="utf-8") == "old checklist"


def test_build_requirement_structure_assets_rejects_parent_mapping_mismatch(tmp_path):
    workbook_path = tmp_path / "review.xlsx"
    checklist_path = tmp_path / "checklist.json"
    _write_structure_review_workbook(workbook_path)
    _write_source_checklist(checklist_path, child_parent="current_gap:GRI2:2-2:b")

    with pytest.raises(ValueError, match="parent mapping mismatch"):
        build_requirement_structure_assets(
            review_workbook=workbook_path,
            source_checklist=checklist_path,
            output_structure=tmp_path / "structure-v2.json",
            output_checklist=tmp_path / "checklist-v2.json",
            expected_review_sha256=sha256(workbook_path.read_bytes()).hexdigest(),
            expected_counts=None,
        )


def test_build_requirement_structure_assets_accepts_flat_disclosure_parent_pointer(
    tmp_path,
):
    workbook_path = tmp_path / "review.xlsx"
    checklist_path = tmp_path / "checklist.json"
    _write_structure_review_workbook(workbook_path)
    _write_source_checklist(
        checklist_path,
        child_parent="current_gap:GRI2:2-2",
    )

    metadata = build_requirement_structure_assets(
        review_workbook=workbook_path,
        source_checklist=checklist_path,
        output_structure=tmp_path / "structure-v2.json",
        output_checklist=tmp_path / "checklist-v2.json",
        expected_review_sha256=sha256(workbook_path.read_bytes()).hexdigest(),
        expected_counts=None,
    )

    assert metadata["normalized_count"] == 1


def test_build_requirement_structure_assets_excludes_non_current_scope_items(tmp_path):
    workbook_path = tmp_path / "review.xlsx"
    checklist_path = tmp_path / "checklist.json"
    output_path = tmp_path / "checklist-v2.json"
    _write_structure_review_workbook(workbook_path)
    _write_source_checklist(checklist_path)
    source = json.loads(checklist_path.read_text(encoding="utf-8"))
    source["requirements"].append(
        {
            **_source_item(
                "watchlist_2027:GRI999:test",
                "watchlist_2027:GRI999",
                "999-1",
                "future requirement",
            ),
            "assessment_mode": "watchlist_2027",
        }
    )
    checklist_path.write_text(json.dumps(source), encoding="utf-8")

    metadata = build_requirement_structure_assets(
        review_workbook=workbook_path,
        source_checklist=checklist_path,
        output_structure=tmp_path / "structure-v2.json",
        output_checklist=output_path,
        expected_review_sha256=sha256(workbook_path.read_bytes()).hexdigest(),
        expected_counts={"standard_unit_count": 4},
    )

    compiled = json.loads(output_path.read_text(encoding="utf-8"))
    assert metadata["standard_unit_count"] == 4
    assert len(compiled["requirements"]) == 4
