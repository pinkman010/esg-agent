from types import SimpleNamespace

import pytest

from src.tools.build_shadow_rag_contexts import build_shadow_context
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
