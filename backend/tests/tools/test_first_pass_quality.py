import csv
from pathlib import Path

from src.tools.first_pass_quality import (
    build_remediation_manifest_rows,
    compare_first_pass_to_after_rules,
    summarize_quality,
    summarize_quality_csv,
)


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_first_pass_quality_counts_manual_gold_fields(tmp_path: Path):
    current = tmp_path / "current.csv"
    after = tmp_path / "after.csv"
    write_csv(
        current,
        [
            {
                "requirement_id": "GRI 414-1-a",
                "verdict": "unknown",
                "source_pdf_page": "",
                "manual_label": "漏检",
                "correct_pdf_pages": "[67]",
                "suggested_verdict": "disclosed",
                "issue_type": "missed_evidence",
            },
            {
                "requirement_id": "GRI 408-1-a-ii",
                "verdict": "disclosed",
                "source_pdf_page": "32",
                "manual_label": "误升",
                "correct_pdf_pages": "[32, 52, 53]",
                "suggested_verdict": "partially_disclosed",
                "issue_type": "false_disclosed",
            },
            {
                "requirement_id": "GRI 413-1-a-v",
                "verdict": "partially_disclosed",
                "source_pdf_page": "42",
                "manual_label": "证据页不完整",
                "correct_pdf_pages": "[14, 42, 43, 44]",
                "suggested_verdict": "partially_disclosed",
                "issue_type": "wrong_source_page",
            },
        ],
    )
    write_csv(
        after,
        [
            {"requirement_id": "GRI 414-1-a", "verdict": "disclosed", "source_pdf_page": "67"},
            {"requirement_id": "GRI 408-1-a-ii", "verdict": "partially_disclosed", "source_pdf_page": "32"},
            {"requirement_id": "GRI 413-1-a-v", "verdict": "partially_disclosed", "source_pdf_page": "14"},
        ],
    )

    result = compare_first_pass_to_after_rules(current, after)

    assert result.first_pass_unknown_count == 1
    assert result.unknown_leakage_count == 1
    assert result.false_disclosed_count == 1
    assert result.wrong_source_page_count == 1
    assert result.after_rules_delta_disclosed == 0


def test_summarize_quality_uses_reviewed_gold_and_route_validity() -> None:
    first_rows = [
        {
            "requirement_id": "GRI 1",
            "verdict": "disclosed",
            "source_pdf_pages": "[10]",
            "current_route_status": "candidate_with_evidence",
        },
        {
            "requirement_id": "GRI 2",
            "verdict": "unknown",
            "source_pdf_pages": "[]",
            "current_route_status": "candidate_without_evidence",
        },
        {
            "requirement_id": "GRI 3",
            "verdict": "partially_disclosed",
            "source_pdf_pages": "[12]",
            "current_route_status": "candidate_with_evidence",
        },
    ]
    reviewed_rows = [
        {
            **first_rows[0],
            "manual_label": "invalid",
            "suggested_verdict": "unknown",
            "issue_type": "false_disclosed",
            "correct_pdf_pages": "[]",
        },
        {
            **first_rows[1],
            "manual_label": "partial",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "unknown_leakage",
            "correct_pdf_pages": "[11]",
        },
        {
            **first_rows[2],
            "manual_label": "partial",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "cross_leaf_missing_items",
            "correct_pdf_pages": "[12]",
        },
    ]

    result = summarize_quality(first_rows, reviewed_rows)

    assert result.manual_gold_available is True
    assert result.false_disclosed_count == 1
    assert result.unknown_leakage_count == 1
    assert result.wrong_source_page_count == 2
    assert result.profile_route_valid_evidence_rate == 0.5
    assert result.cross_leaf_missing_items_count == 1
    assert result.guardrail_as_evidence_count == 0


def test_summarize_quality_marks_incomplete_manual_gold() -> None:
    first_rows = [{"requirement_id": "GRI 1", "verdict": "unknown"}]
    reviewed_rows = [{"requirement_id": "GRI 1", "verdict": "unknown", "manual_label": ""}]

    result = summarize_quality(first_rows, reviewed_rows)

    assert result.manual_gold_available is False
    assert result.profile_route_valid_evidence_rate is None


def test_summarize_quality_csv_reads_manual_fields_from_reviewed_file(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    reviewed = tmp_path / "reviewed.csv"
    write_csv(first, [{"requirement_id": "GRI 1", "verdict": "unknown", "source_pdf_pages": "[]"}])
    write_csv(
        reviewed,
        [
            {
                "requirement_id": "GRI 1",
                "verdict": "unknown",
                "source_pdf_pages": "[]",
                "manual_label": "partial",
                "correct_pdf_pages": "[11]",
                "suggested_verdict": "partially_disclosed",
                "issue_type": "missed_evidence",
            }
        ],
    )

    result = summarize_quality_csv(first, reviewed)

    assert result.manual_gold_available is True
    assert result.unknown_leakage_count == 1


def test_complete_manual_gold_uses_primary_issue_and_actual_unknown_transition() -> None:
    first_rows = [
        {
            "requirement_id": "GRI 1",
            "verdict": "partially_disclosed",
            "source_pdf_pages": "[10]",
            "current_route_status": "candidate_with_evidence",
        },
        {
            "requirement_id": "GRI 2",
            "verdict": "partially_disclosed",
            "source_pdf_pages": "[12]",
            "current_route_status": "candidate_with_evidence",
        },
    ]
    reviewed_rows = [
        {
            **first_rows[0],
            "manual_label": "partial",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "acceptable",
            "correct_pdf_pages": "[11]",
        },
        {
            **first_rows[1],
            "manual_label": "partial",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "missed_evidence",
            "correct_pdf_pages": "[12]",
        },
    ]

    result = summarize_quality(first_rows, reviewed_rows)

    assert result.wrong_source_page_count == 1
    assert result.unknown_leakage_count == 0
    assert result.profile_route_valid_evidence_rate == 0.5


def test_build_remediation_manifest_preserves_manual_gold_and_adds_metadata() -> None:
    first_rows = [
        {
            "requirement_id": "GRI 414-1-a",
            "verdict": "disclosed",
            "source_pdf_page": "31",
        },
        {
            "requirement_id": "GRI 414-1-a",
            "verdict": "disclosed",
            "source_pdf_page": "32",
        },
    ]
    reviewed_rows = [
        {
            "requirement_id": "GRI 414-1-a",
            "verdict": "disclosed",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "false_disclosed",
            "correct_pdf_pages": "[31]",
            "manual_label": "partial",
        }
    ]

    rows = build_remediation_manifest_rows(first_rows, reviewed_rows)

    assert rows == [
        {
            "requirement_id": "GRI 414-1-a",
            "current_verdict": "disclosed",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "false_disclosed",
            "current_source_pdf_pages": "[31, 32]",
            "correct_pdf_pages": "[31]",
            "semantic_group": "supplier_assessment",
            "evidence_kinds": '["kpi_value"]',
            "remediation_group": "precision_gate",
        }
    ]


def test_remediation_metrics_compare_new_output_to_manual_gold() -> None:
    first_rows = [
        {
            "requirement_id": "GRI 404-2-a",
            "verdict": "partially_disclosed",
            "source_pdf_pages": "[36]",
            "missing_items": '["员工技能提升项目的内容和覆盖范围", "持续就业能力支持说明"]',
        },
        {
            "requirement_id": "GRI 2",
            "verdict": "unknown",
            "source_pdf_pages": "[]",
            "missing_items": "[]",
        },
    ]
    reviewed_rows = [
        {
            "requirement_id": "GRI 404-2-a",
            "manual_label": "partial",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "cross_leaf_missing_items",
            "correct_pdf_pages": "[36]",
        },
        {
            "requirement_id": "GRI 2",
            "manual_label": "unknown",
            "suggested_verdict": "unknown",
            "issue_type": "false_disclosed",
            "correct_pdf_pages": "[]",
        },
    ]

    result = summarize_quality(first_rows, reviewed_rows)

    assert result.false_disclosed_count == 0
    assert result.wrong_source_page_count == 0
    assert result.cross_leaf_missing_items_count == 0


def test_cross_leaf_metric_ignores_compilation_guardrail_items() -> None:
    first_rows = [
        {
            "requirement_id": "GRI 306-3-a",
            "verdict": "partially_disclosed",
            "source_pdf_pages": "[64]",
            "missing_items": '["废弃物组成拆分", "exclude effluent unless national law requires inclusion in total waste", "1000 kilograms per metric ton or metric tons directly"]',
        }
    ]
    reviewed_rows = [
        {
            "requirement_id": "GRI 306-3-a",
            "manual_label": "partial",
            "suggested_verdict": "partially_disclosed",
            "issue_type": "cross_leaf_missing_items",
            "correct_pdf_pages": "[64]",
        }
    ]

    result = summarize_quality(first_rows, reviewed_rows)

    assert result.cross_leaf_missing_items_count == 0
