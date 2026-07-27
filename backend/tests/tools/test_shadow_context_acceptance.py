import csv
import json

import pytest

from src.tools.shadow_context_acceptance import (
    audit_contexts,
    build_acceptance_summary,
    build_comparison_case,
    compute_method_metrics,
    load_comparison_inputs,
    render_acceptance_report,
)


def test_comparison_metrics_use_only_cases_with_gold_pages():
    cases = [
        build_comparison_case(
            report_id="report-envision",
            requirement_id="GRI 305-1-a",
            gold_pages=[40, 41],
            rule_pages=[40, 8],
            vector_pages=[41, 9, 40],
            hybrid_pages=[40, 41, 9],
            context_hash="a" * 64,
            unresolved_rule_pages=[],
        ),
        build_comparison_case(
            report_id="report-envision",
            requirement_id="GRI 305-2-a",
            gold_pages=[],
            rule_pages=[42],
            vector_pages=[42],
            hybrid_pages=[42],
            context_hash="b" * 64,
            unresolved_rule_pages=[],
        ),
    ]

    rule = compute_method_metrics(cases, method="rule")
    vector = compute_method_metrics(cases, method="vector")
    hybrid = compute_method_metrics(cases, method="hybrid")

    assert rule["evaluated_case_count"] == 1
    assert rule["no_gold_page_case_count"] == 1
    assert rule["hit_at_1"] == 1.0
    assert rule["recall_at_1"] == 0.5
    assert vector["recall_at_3"] == 1.0
    assert hybrid["recall_at_3"] == 1.0
    assert hybrid["mrr"] == 1.0


def _valid_context() -> dict:
    return {
        "report_id": "report-envision",
        "requirement_id": "GRI 305-1-a",
        "context_hash": "a" * 64,
        "retrieval_mode": "hybrid_rrf",
        "vector_pool_k": 10,
        "context_k": 5,
        "top_k": 5,
        "rrf_rule_weight": 2.0,
        "rrf_vector_weight": 1.0,
        "rrf_constant": 60,
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "unresolved_rule_pages": [],
        "evidence": [
            {
                "chunk_id": f"chunk-{page}",
                "shadow_evidence_id": f"shadow-chunk:chunk-{page}",
                "source_page": page,
                "retrieval_sources": ["rule"],
                "rule_rank": page,
                "vector_rank": None,
                "fusion_score": 2 / (60 + page),
            }
            for page in range(1, 6)
        ],
    }


def test_build_comparison_case_classifies_hybrid_gain_and_loss():
    gain = build_comparison_case(
        report_id="report-envision",
        requirement_id="GRI 305-1-a",
        gold_pages=[40],
        rule_pages=[8],
        vector_pages=[40],
        hybrid_pages=[40, 8],
        context_hash="a" * 64,
        unresolved_rule_pages=[],
    )
    loss = build_comparison_case(
        report_id="report-envision",
        requirement_id="GRI 305-2-a",
        gold_pages=[41],
        rule_pages=[41],
        vector_pages=[9],
        hybrid_pages=[9],
        context_hash="b" * 64,
        unresolved_rule_pages=[],
    )

    assert gain["comparison_bucket"] == "hybrid_gain"
    assert loss["comparison_bucket"] == "hybrid_loss"


def test_audit_contexts_accepts_valid_fixed_hybrid_context():
    audit = audit_contexts(
        [_valid_context()],
        report_id="report-envision",
        report_total_pages=78,
        expected_count=1,
    )

    assert audit == {
        "context_count": 1,
        "unique_requirement_count": 1,
        "unique_context_hash_count": 1,
        "duplicate_page_context_count": 0,
        "unresolved_rule_page_context_count": 0,
        "out_of_range_page_count": 0,
        "invalid_shadow_evidence_id_count": 0,
        "invalid_rrf_evidence_count": 0,
        "context_size_not_5_count": 0,
    }


def test_audit_contexts_rejects_duplicate_pages_and_foreign_report():
    context = _valid_context()
    context["report_id"] = "report-other"
    context["evidence"][1]["source_page"] = 1

    with pytest.raises(ValueError, match="report_id"):
        audit_contexts(
            [context],
            report_id="report-envision",
            report_total_pages=78,
            expected_count=1,
            require_exact_context_size=False,
        )


def test_audit_contexts_rejects_duplicate_pages():
    context = _valid_context()
    context["evidence"][1]["source_page"] = 1

    with pytest.raises(ValueError, match="duplicate source pages"):
        audit_contexts(
            [context],
            report_id="report-envision",
            report_total_pages=78,
            expected_count=1,
        )


def test_audit_contexts_rejects_shadow_id_without_matching_chunk():
    context = _valid_context()
    context["evidence"][0]["chunk_id"] = "chunk-1"
    context["evidence"][0]["shadow_evidence_id"] = "shadow-chunk:"

    with pytest.raises(ValueError, match="shadow evidence id"):
        audit_contexts(
            [context],
            report_id="report-envision",
            report_total_pages=78,
            expected_count=1,
        )


def test_audit_contexts_rejects_rrf_parameter_drift():
    context = _valid_context()
    context["rrf_rule_weight"] = 1.0

    with pytest.raises(ValueError, match="RRF metadata"):
        audit_contexts(
            [context],
            report_id="report-envision",
            report_total_pages=78,
            expected_count=1,
        )


def test_audit_contexts_rejects_embedding_identity_drift():
    context = _valid_context()
    context["model"] = "other-model"

    with pytest.raises(ValueError, match="RRF metadata"):
        audit_contexts(
            [context],
            report_id="report-envision",
            report_total_pages=78,
            expected_count=1,
        )


def test_audit_contexts_rejects_invalid_rrf_evidence_score():
    context = _valid_context()
    context["evidence"][0]["fusion_score"] = 0.0

    with pytest.raises(ValueError, match="RRF evidence"):
        audit_contexts(
            [context],
            report_id="report-envision",
            report_total_pages=78,
            expected_count=1,
        )


def test_load_comparison_cases_joins_by_requirement_id(tmp_path):
    retrieval_path = tmp_path / "cases.csv"
    contexts_path = tmp_path / "contexts.jsonl"
    with retrieval_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "report_id",
                "requirement_id",
                "gold_pages",
                "rule_pages",
                "vector_source_pages",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "report_id": "report-envision",
                "requirement_id": "GRI 2-1-a",
                "gold_pages": "[1, 3]",
                "rule_pages": "[3, 6]",
                "vector_source_pages": "[1, 8, 3]",
            }
        )
    contexts_path.write_text(
        json.dumps(
            {
                "report_id": "report-envision",
                "requirement_id": "GRI 2-1-a",
                "context_hash": "a" * 64,
                "unresolved_rule_pages": [],
                "evidence": [
                    {"source_page": 3},
                    {"source_page": 1},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cases, contexts = load_comparison_inputs(
        retrieval_path,
        contexts_path,
        report_id="report-envision",
        expected_count=1,
    )

    assert cases[0]["rule_pages"] == [3, 6]
    assert cases[0]["vector_pages"] == [1, 8, 3]
    assert cases[0]["hybrid_pages"] == [3, 1]
    assert cases[0]["context_size"] == 2
    assert cases[0]["duplicate_page_count"] == 0
    assert len(contexts) == 1


def test_compute_method_metrics_limits_mrr_to_top_five():
    metrics = compute_method_metrics(
        [
            {
                "gold_pages": [6],
                "rule_pages": [1, 2, 3, 4, 5, 6],
            }
        ],
        method="rule",
    )

    assert metrics["hit_at_5"] == 0.0
    assert metrics["mrr"] == 0.0


def test_load_comparison_inputs_reports_invalid_json_line(tmp_path):
    retrieval_path = tmp_path / "cases.csv"
    retrieval_path.write_text(
        "report_id,requirement_id\nreport-envision,GRI 2-1-a\n",
        encoding="utf-8",
    )
    contexts_path = tmp_path / "contexts.jsonl"
    contexts_path.write_text("\n{invalid}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 2"):
        load_comparison_inputs(
            retrieval_path,
            contexts_path,
            report_id="report-envision",
            expected_count=1,
        )


def test_build_acceptance_summary_requires_hybrid_not_below_rule():
    cases = [
        build_comparison_case(
            report_id="report-envision",
            requirement_id="GRI 305-1-a",
            gold_pages=[40],
            rule_pages=[40],
            vector_pages=[8],
            hybrid_pages=[8],
            context_hash="a" * 64,
            unresolved_rule_pages=[],
        )
    ]

    summary = build_acceptance_summary(
        report_id="report-envision",
        run_metadata={
            "git_head": "0cf3cbc",
            "input_manifest_path": (
                "tmp/embedding/envision_phase1_5_input_manifest.json"
            ),
            "retrieval_mode": "hybrid_rrf",
            "provider": "siliconflow",
            "model": "BAAI/bge-m3",
            "vector_pool_k": 10,
            "context_k": 5,
            "rrf_rule_weight": 2.0,
            "rrf_vector_weight": 1.0,
            "rrf_constant": 60,
            "git_dirty": True,
            "git_status_sha256": "b" * 64,
        },
        cases=cases,
        context_audit={
            "context_count": 1,
            "unique_requirement_count": 1,
            "unique_context_hash_count": 1,
            "duplicate_page_context_count": 0,
            "unresolved_rule_page_context_count": 0,
            "out_of_range_page_count": 0,
            "invalid_shadow_evidence_id_count": 0,
            "invalid_rrf_evidence_count": 0,
            "context_size_not_5_count": 0,
        },
        deterministic_hash_mismatch_count=0,
        formal_table_counts_before={"assessments": 10},
        formal_table_counts_after={"assessments": 10},
        embedding_enabled=False,
        expected_count=1,
        expected_evaluated_case_count=1,
    )

    assert summary["gates"]["hybrid_hit_at_5_not_below_rule"] is False
    assert summary["ok"] is False
    report = render_acceptance_report(summary)
    assert "未通过" in report
    assert "不构成 GRI 专家认证" in report
    assert "无 gold requirement 不进入召回指标分母" in report
    assert "0cf3cbc" in report
    assert "`vector_pool_k=10`" in report
    assert "工作区未提交变更：是" in report


def test_build_acceptance_summary_passes_all_engineering_gates():
    cases = [
        build_comparison_case(
            report_id="report-envision",
            requirement_id="GRI 305-1-a",
            gold_pages=[40],
            rule_pages=[8],
            vector_pages=[40],
            hybrid_pages=[40, 8],
            context_hash="a" * 64,
            unresolved_rule_pages=[],
        )
    ]

    summary = build_acceptance_summary(
        report_id="report-envision",
        run_metadata={
            "git_head": "0cf3cbc",
            "input_manifest_path": "tmp/embedding/manifest.json",
            "retrieval_mode": "hybrid_rrf",
            "provider": "siliconflow",
            "model": "BAAI/bge-m3",
            "vector_pool_k": 10,
            "context_k": 5,
            "rrf_rule_weight": 2.0,
            "rrf_vector_weight": 1.0,
            "rrf_constant": 60,
            "git_dirty": True,
            "git_status_sha256": "b" * 64,
        },
        cases=cases,
        context_audit={
            "context_count": 1,
            "unique_requirement_count": 1,
            "unique_context_hash_count": 1,
            "duplicate_page_context_count": 0,
            "unresolved_rule_page_context_count": 0,
            "out_of_range_page_count": 0,
            "invalid_shadow_evidence_id_count": 0,
            "invalid_rrf_evidence_count": 0,
            "context_size_not_5_count": 0,
        },
        deterministic_hash_mismatch_count=0,
        formal_table_counts_before={"assessments": 10},
        formal_table_counts_after={"assessments": 10},
        embedding_enabled=False,
        expected_count=1,
        expected_evaluated_case_count=1,
    )

    assert summary["ok"] is True
    assert all(summary["gates"].values())


def test_build_acceptance_summary_rejects_missing_gold_coverage():
    case = build_comparison_case(
        report_id="report-envision",
        requirement_id="GRI 305-1-a",
        gold_pages=[],
        rule_pages=[40],
        vector_pages=[40],
        hybrid_pages=[40],
        context_hash="a" * 64,
        unresolved_rule_pages=[],
    )

    summary = build_acceptance_summary(
        report_id="report-envision",
        run_metadata={
            "git_head": "a" * 40,
            "input_manifest_path": "tmp/embedding/manifest.json",
            "retrieval_mode": "hybrid_rrf",
            "provider": "siliconflow",
            "model": "BAAI/bge-m3",
            "vector_pool_k": 10,
            "context_k": 5,
            "rrf_rule_weight": 2.0,
            "rrf_vector_weight": 1.0,
            "rrf_constant": 60,
            "git_dirty": True,
            "git_status_sha256": "b" * 64,
        },
        cases=[case],
        context_audit={
            "context_count": 1,
            "unique_requirement_count": 1,
            "unique_context_hash_count": 1,
            "duplicate_page_context_count": 0,
            "unresolved_rule_page_context_count": 0,
            "out_of_range_page_count": 0,
            "invalid_shadow_evidence_id_count": 0,
            "invalid_rrf_evidence_count": 0,
            "context_size_not_5_count": 0,
        },
        deterministic_hash_mismatch_count=0,
        formal_table_counts_before={"assessments": 10},
        formal_table_counts_after={"assessments": 10},
        embedding_enabled=False,
        expected_count=1,
        expected_evaluated_case_count=1,
    )

    assert summary["gates"]["evaluated_case_count_matches_expected"] is False
    assert summary["ok"] is False
