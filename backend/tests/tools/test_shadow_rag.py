from types import SimpleNamespace

import pytest

from src.tools.build_shadow_rag_contexts import (
    build_shadow_context,
    fuse_shadow_hits,
    load_shadow_contexts_from_cases,
)
from src.tools.evaluate_shadow_rag import (
    evaluate_shadow_contexts,
    validate_shadow_response,
)
from src.tools.llm_client import LLMClient, ModelCallBlocked


def test_build_context_pack_keeps_shadow_evidence_separate():
    context = build_shadow_context(
        report_id="report-envision",
        requirement_id="GRI 305-1-a",
        requirement_text="披露范围一温室气体排放。",
        hits=[
            {
                "chunk_id": "chunk-1",
                "source_page": 40,
                "score": 0.91,
                "text": "范围一温室气体排放为……",
            }
        ],
        gold_pages=[40],
        manual_suggested_verdict="disclosed",
    )

    assert context["evidence"][0]["shadow_evidence_id"] == "shadow-chunk:chunk-1"
    assert context["evidence"][0]["source_page"] == 40
    assert "evidence_id" not in context["evidence"][0]
    assert context["gold_pages"] == [40]
    assert "retrieval_mode" not in context
    assert context["context_hash"] == (
        "c46faa0e7bfe9f1c0578b3c2541c4214"
        "188f726ebe6fd5fff38bed89db9a8b4a"
    )


def test_fuse_shadow_hits_uses_rrf_two_to_one_and_deduplicates_chunks():
    hits, unresolved = fuse_shadow_hits(
        rule_pages=[10, 20],
        vector_hits=[
            {
                "chunk_id": "chunk-vector-only",
                "source_page": 30,
                "score": 0.95,
                "text": "向量独占候选",
            },
            {
                "chunk_id": "chunk-both",
                "source_page": 10,
                "score": 0.90,
                "text": "双路候选",
            },
        ],
        report_chunks=[
            {
                "chunk_id": "chunk-both",
                "source_page": 10,
                "text": "双路候选",
            },
            {
                "chunk_id": "chunk-rule-only",
                "source_page": 20,
                "text": "规则独占候选",
            },
        ],
        vector_pool_k=10,
        context_k=5,
        rule_weight=2,
        vector_weight=1,
        rrf_constant=60,
    )

    assert unresolved == []
    assert [hit["chunk_id"] for hit in hits] == [
        "chunk-both",
        "chunk-rule-only",
        "chunk-vector-only",
    ]
    assert hits[0]["retrieval_sources"] == ["rule", "vector"]
    assert hits[0]["rule_rank"] == 1
    assert hits[0]["vector_rank"] == 2
    assert hits[0]["fusion_score"] == pytest.approx(
        2 / 61 + 1 / 62
    )
    assert hits[1]["retrieval_sources"] == ["rule"]
    assert hits[2]["retrieval_sources"] == ["vector"]


def test_fuse_shadow_hits_limits_vector_pool_and_final_context():
    vector_hits = [
        {
            "chunk_id": f"chunk-{index:02d}",
            "source_page": index,
            "score": 1 - index / 100,
            "text": f"候选 {index}",
        }
        for index in range(1, 13)
    ]

    hits, unresolved = fuse_shadow_hits(
        rule_pages=[],
        vector_hits=vector_hits,
        report_chunks=[],
        vector_pool_k=10,
        context_k=5,
    )

    assert unresolved == []
    assert [hit["chunk_id"] for hit in hits] == [
        "chunk-01",
        "chunk-02",
        "chunk-03",
        "chunk-04",
        "chunk-05",
    ]
    assert all(hit["vector_rank"] <= 10 for hit in hits)


def test_fuse_shadow_hits_reports_unresolved_rule_pages():
    hits, unresolved = fuse_shadow_hits(
        rule_pages=[10, 99],
        vector_hits=[],
        report_chunks=[
            {
                "chunk_id": "chunk-10",
                "source_page": 10,
                "text": "第十页",
            }
        ],
    )

    assert [hit["chunk_id"] for hit in hits] == ["chunk-10"]
    assert unresolved == [99]


def test_fuse_shadow_hits_uses_vector_text_for_rule_page_missing_from_database():
    hits, unresolved = fuse_shadow_hits(
        rule_pages=[10],
        vector_hits=[
            {
                "chunk_id": "chunk-page-10-vector",
                "source_page": 10,
                "score": 0.92,
                "text": "第十页向量命中片段",
            }
        ],
        report_chunks=[
            {
                "chunk_id": "chunk-other-page",
                "source_page": 20,
                "text": "其他页面正文",
            }
        ],
    )

    assert unresolved == []
    assert [hit["chunk_id"] for hit in hits] == [
        "chunk-page-10-vector"
    ]
    assert hits[0]["retrieval_sources"] == ["rule", "vector"]
    assert hits[0]["fusion_score"] == pytest.approx(3 / 61)


def test_fuse_shadow_hits_keeps_one_vector_preferred_chunk_per_page():
    hits, unresolved = fuse_shadow_hits(
        rule_pages=[10, 20],
        vector_hits=[
            {
                "chunk_id": "chunk-page-10-vector",
                "source_page": 10,
                "score": 0.92,
                "text": "第十页向量命中片段",
            },
            {
                "chunk_id": "chunk-page-10-lower",
                "source_page": 10,
                "score": 0.80,
                "text": "第十页次级向量片段",
            },
        ],
        report_chunks=[
            {
                "chunk_id": "chunk-page-10-rule",
                "source_page": 10,
                "text": "第十页规则片段",
            },
            {
                "chunk_id": "chunk-page-10-vector",
                "source_page": 10,
                "text": "第十页向量命中片段",
            },
            {
                "chunk_id": "chunk-page-20-short",
                "source_page": 20,
                "text": "短",
            },
            {
                "chunk_id": "chunk-page-20-long",
                "source_page": 20,
                "text": "第二十页较长且信息更完整的规则片段",
            },
        ],
    )

    assert unresolved == []
    assert [hit["source_page"] for hit in hits] == [10, 20]
    assert hits[0]["chunk_id"] == "chunk-page-10-vector"
    assert hits[0]["retrieval_sources"] == ["rule", "vector"]
    assert hits[1]["chunk_id"] == "chunk-page-20-long"


def test_load_hybrid_context_rejects_empty_report_chunk_set(tmp_path):
    with pytest.raises(
        ValueError,
        match="hybrid_rrf requires document chunks",
    ):
        load_shadow_contexts_from_cases(
            tmp_path / "missing.csv",
            report_id="report-missing",
            retrieval_mode="hybrid_rrf",
            report_chunks=[],
        )


def test_load_hybrid_context_from_cases_uses_rrf_metadata(
    tmp_path,
):
    cases_path = tmp_path / "cases.csv"
    cases_path.write_text(
        (
            "report_id,requirement_id,query_text,gold_pages,rule_pages,"
            "vector_chunk_ids,vector_source_pages,vector_scores,vector_texts\n"
            'report-envision,GRI 2-1-a,企业名称,[10],"[10, 20]",'
            '"[""chunk-vector""]","[30]","[0.9]",'
            '"[""向量正文""]"\n'
        ),
        encoding="utf-8",
    )

    contexts = load_shadow_contexts_from_cases(
        cases_path,
        report_id="report-envision",
        retrieval_mode="hybrid_rrf",
        report_chunks=[
            {
                "chunk_id": "chunk-rule-10",
                "source_page": 10,
                "text": "规则正文十",
            },
            {
                "chunk_id": "chunk-rule-20",
                "source_page": 20,
                "text": "规则正文二十",
            },
        ],
        vector_pool_k=10,
        context_k=2,
    )

    context = contexts[0]
    assert context["retrieval_mode"] == "hybrid_rrf"
    assert context["vector_pool_k"] == 10
    assert context["context_k"] == 2
    assert context["top_k"] == 2
    assert [
        item["chunk_id"] for item in context["evidence"]
    ] == ["chunk-rule-10", "chunk-rule-20"]
    assert context["unresolved_rule_pages"] == []


def test_validate_shadow_response_marks_out_of_scope_citation():
    context = build_shadow_context(
        report_id="report-envision",
        requirement_id="GRI 305-1-a",
        requirement_text="披露范围一温室气体排放。",
        hits=[
            {
                "chunk_id": "chunk-1",
                "source_page": 40,
                "score": 0.91,
                "text": "范围一温室气体排放为……",
            }
        ],
    )

    result = validate_shadow_response(
        context,
        {
            "suggested_verdict": "disclosed",
            "rationale": "存在直接证据。",
            "cited_evidence_ids": ["shadow-chunk:outside"],
            "cited_pdf_pages": [40],
            "missing_items": [],
        },
    )

    assert result["shadow_status"] == "guardrail_failed"
    assert result["shadow_suggested_verdict"] is None
    assert "invalid_shadow_citation" in result["shadow_guardrail_codes"]


def test_evaluate_shadow_contexts_blocks_without_confirmation():
    calls = []
    client = LLMClient(
        model="deepseek-v4-flash",
        completion_factory=lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(ModelCallBlocked):
        evaluate_shadow_contexts(
            [],
            client=client,
            confirm_llm=False,
        )

    assert calls == []


def test_evaluate_shadow_contexts_uses_fake_llm_without_database_writes():
    def complete(**_kwargs):
        return SimpleNamespace(
            model="deepseek-v4-flash",
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=(
                            '{"suggested_verdict":"disclosed",'
                            '"rationale":"存在直接证据。",'
                            '"cited_evidence_ids":["shadow-chunk:chunk-1"],'
                            '"cited_pdf_pages":[40],'
                            '"missing_items":[]}'
                        )
                    ),
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )

    client = LLMClient(
        model="deepseek-v4-flash",
        completion_factory=complete,
        retry_delay_seconds=0,
    )
    context = build_shadow_context(
        report_id="report-envision",
        requirement_id="GRI 305-1-a",
        requirement_text="披露范围一温室气体排放。",
        hits=[
            {
                "chunk_id": "chunk-1",
                "source_page": 40,
                "score": 0.91,
                "text": "范围一温室气体排放为……",
            }
        ],
        gold_pages=[40],
        manual_suggested_verdict="disclosed",
    )

    rows, summary = evaluate_shadow_contexts(
        [context],
        client=client,
        confirm_llm=True,
    )

    assert rows[0]["shadow_status"] == "succeeded"
    assert rows[0]["shadow_suggested_verdict"] == "disclosed"
    assert summary["evaluated_count"] == 1
    assert summary["false_disclosed_count"] == 0
    assert summary["wrong_source_page_count"] == 0
