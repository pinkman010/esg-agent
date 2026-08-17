import json
import threading
import time

import pytest

from src.domain.enums import (
    AISuggestionStatus,
    AssessmentVerdict,
    EvidenceSourceMethod,
    PageQualityFlag,
    RiskLevel,
)
from src.domain.models import DisclosureAssessment, DisclosureTask, EvidenceItem
from src.services.ai_assessment_service import (
    AIAssessmentCandidate,
    AIAssessmentService,
)
from src.tools.llm_client import LLMCompletionResult


def _evidence(
    evidence_id: str = "evidence-1",
    page: int = 41,
    *,
    evidence_type: str | None = "substantive_report_evidence",
    source_text: str = "报告披露了控制措施。",
    metadata: dict[str, object] | None = None,
    quality_flags: list[PageQualityFlag] | None = None,
) -> EvidenceItem:
    evidence_metadata = dict(metadata or {})
    if evidence_type is not None:
        evidence_metadata.setdefault("evidence_type", evidence_type)
    return EvidenceItem(
        evidence_id=evidence_id,
        run_id="run-1",
        report_id="report-1",
        source_text=source_text,
        source_page=page,
        source_pdf_page=page,
        source_file_hash="f" * 64,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        quality_flags=quality_flags or [],
        metadata=evidence_metadata,
    )


def _candidate(
    requirement_id: str = "GRI 403-9-d",
    *,
    structure_status: str = "verified",
    review_priority: RiskLevel = RiskLevel.HIGH,
    evidence: list[EvidenceItem] | None = None,
    verdict: AssessmentVerdict | None = None,
) -> AIAssessmentCandidate:
    evidence = [_evidence()] if evidence is None else evidence
    verdict = verdict or (
        AssessmentVerdict.PARTIALLY_DISCLOSED if evidence else AssessmentVerdict.UNKNOWN
    )
    task = DisclosureTask(
        task_id=f"task-{requirement_id}",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 403-9",
        requirement_id=requirement_id,
        requirement_text="披露为消除危险并尽量降低风险而采取的行动。",
        source_requirement_text="为消除危险并尽量降低风险而采取的行动",
        context_requirement_ids=["GRI 403-9"],
        structure_status=structure_status,
    )
    assessment = DisclosureAssessment(
        assessment_id=f"assessment-{requirement_id}",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 403-9",
        requirement_id=requirement_id,
        verdict=verdict,
        rationale="规则基线结论。",
        evidence=evidence,
        missing_items=["控制层级"],
    )
    return AIAssessmentCandidate(
        task=task,
        assessment=assessment,
        review_priority=review_priority,
    )


class FakeLLMClient:
    model = "deepseek-v4-flash"

    def __init__(self, response: dict | None = None):
        self.calls = []
        self.response = response or {
            "suggested_verdict": "disclosed",
            "evidence_ids": ["evidence-1"],
            "evidence_pdf_pages": [41],
            "rationale_zh": "报告原文直接披露了控制措施。",
            "missing_items_zh": [],
            "confidence": 0.9,
        }

    def complete_json(self, *, messages, confirm_llm):
        self.calls.append({"messages": messages, "confirm_llm": confirm_llm})
        return LLMCompletionResult(
            content=self.response,
            model=self.model,
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=12,
            retry_count=0,
        )


def test_should_call_only_independent_high_or_medium_items_with_direct_evidence():
    service = AIAssessmentService(FakeLLMClient())

    assert service.should_call(_candidate(structure_status="verified")) is True
    assert service.should_call(
        _candidate(structure_status="normalized", review_priority=RiskLevel.MEDIUM)
    ) is True
    assert service.should_call(_candidate(structure_status="context_only")) is False
    assert service.should_call(_candidate(structure_status="method_pending")) is False
    assert service.should_call(_candidate(review_priority=RiskLevel.LOW)) is False
    assert service.should_call(_candidate(evidence=[])) is False
    assert service.should_call(
        _candidate(evidence=[_evidence(evidence_type="index_statement")])
    ) is False


@pytest.mark.parametrize(
    ("metadata", "quality_flags", "expected"),
    [
        ({"evidence_type": "substantive_report_evidence"}, [], True),
        ({}, [], True),
        ({"evidence_type": "index_statement"}, [], False),
        ({"evidence_type": "omission_note"}, [], False),
        ({}, [PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED], False),
        (
            {"evidence_type": "substantive_report_evidence"},
            [PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED],
            False,
        ),
        (
            {
                "retrieval_strategy": "index_page_bounded",
                "candidate_page_source": "gri_report_index",
            },
            [PageQualityFlag.DIGITAL_TEXT],
            True,
        ),
    ],
)
def test_should_call_rejects_unresolved_image_body_without_treating_routes_as_types(
    metadata,
    quality_flags,
    expected,
):
    service = AIAssessmentService(FakeLLMClient())
    evidence = _evidence(
        evidence_type=None,
        metadata=metadata,
        quality_flags=quality_flags,
    )

    assert service.should_call(_candidate(evidence=[evidence])) is expected


def test_assess_candidates_skips_envision_assurance_page_without_image_body_text():
    client = FakeLLMClient()
    service = AIAssessmentService(client)
    candidates = [
        _candidate(
            requirement_id=requirement_id,
            evidence=[
                _evidence(
                    evidence_id=f"evidence-{requirement_id}",
                    page=77,
                    evidence_type=None,
                    source_text="目录 独立有限鉴证报告",
                    metadata={
                        "retrieval_strategy": "index_page_bounded",
                        "candidate_page_source": "gri_report_index",
                    },
                    quality_flags=[
                        PageQualityFlag.DIGITAL_TEXT,
                        PageQualityFlag.SHORT_TEXT,
                        PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED,
                    ],
                )
            ],
        )
        for requirement_id in (
            "GRI 2-5-a",
            "GRI 2-5-b-i",
            "GRI 2-5-b-ii",
            "GRI 2-5-b-iii",
        )
    ]

    suggestions = service.assess_candidates(candidates, confirm_llm=True)

    assert client.calls == []
    assert len(suggestions) == 4
    assert {item.status for item in suggestions} == {AISuggestionStatus.SKIPPED}
    assert {
        code for item in suggestions for code in item.guardrail_codes
    } == {"no_substantive_evidence"}


def test_prompt_contract_is_bounded_deterministic_and_contains_required_json_example():
    evidence = [
        _evidence(f"evidence-{index}", 40 + index, source_text="证据" * 1000)
        for index in range(1, 7)
    ]
    service = AIAssessmentService(FakeLLMClient())

    messages, input_hash = service.build_messages(_candidate(evidence=evidence))
    repeated_messages, repeated_hash = service.build_messages(_candidate(evidence=evidence))

    assert messages == repeated_messages
    assert input_hash == repeated_hash
    assert len(input_hash) == 64
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "JSON" in messages[0]["content"]
    assert "不得判断适用性" in messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert payload["requirement_id"] == "GRI 403-9-d"
    assert payload["effective_requirement_text"]
    assert payload["source_requirement_text"]
    assert payload["context_requirement_ids"] == ["GRI 403-9"]
    assert payload["rule_missing_items"] == ["控制层级"]
    assert len(payload["evidence"]) == 5
    assert all(len(item["source_text"]) <= 1200 for item in payload["evidence"])
    assert payload["required_json_output"]["suggested_verdict"].startswith("disclosed")


def test_validate_response_rejects_out_of_scope_evidence_and_page():
    service = AIAssessmentService(FakeLLMClient())
    candidate = _candidate()

    suggestion = service.validate_response(
        response={
            "suggested_verdict": "disclosed",
            "evidence_ids": ["invented-evidence"],
            "evidence_pdf_pages": [999],
            "rationale_zh": "已完整披露。",
            "missing_items_zh": [],
            "confidence": 0.99,
        },
        candidate=candidate,
        input_hash="a" * 64,
    )

    assert suggestion.status is AISuggestionStatus.FAILED
    assert "evidence_reference_out_of_scope" in suggestion.guardrail_codes
    assert suggestion.raw_response["evidence_ids"] == ["invented-evidence"]
    assert candidate.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED


@pytest.mark.parametrize(
    ("response", "guardrail_code"),
    [
        (
            {
                "suggested_verdict": "disclosed",
                "evidence_ids": ["evidence-1"],
                "evidence_pdf_pages": [42],
                "rationale_zh": "页码不匹配。",
                "missing_items_zh": [],
                "confidence": 0.8,
            },
            "evidence_page_mismatch",
        ),
        (
            {
                "suggested_verdict": "partially_disclosed",
                "evidence_ids": ["evidence-1"],
                "evidence_pdf_pages": [41],
                "rationale_zh": "部分披露。",
                "missing_items_zh": [],
                "confidence": 0.8,
            },
            "partial_without_missing_items",
        ),
        (
            {
                "suggested_verdict": "disclosed",
                "evidence_ids": ["evidence-1"],
                "evidence_pdf_pages": [41],
                "rationale_zh": "仅索引。",
                "missing_items_zh": [],
                "confidence": 0.8,
            },
            "disclosed_without_substantive_evidence",
        ),
        (
            {
                "suggested_verdict": "disclosed",
                "evidence_ids": ["evidence-1"],
                "evidence_pdf_pages": [41],
                "rationale_zh": "置信度非法。",
                "missing_items_zh": [],
                "confidence": 1.1,
            },
            "response_schema_invalid",
        ),
    ],
)
def test_validate_response_applies_sufficiency_and_schema_guardrails(
    response, guardrail_code
):
    evidence = [_evidence(evidence_type="index_statement")] if "仅索引" in response["rationale_zh"] else None
    candidate = _candidate(evidence=evidence)
    service = AIAssessmentService(FakeLLMClient())

    suggestion = service.validate_response(
        response=response,
        candidate=candidate,
        input_hash="a" * 64,
    )

    assert suggestion.status is AISuggestionStatus.FAILED
    assert guardrail_code in suggestion.guardrail_codes


def test_unknown_response_may_succeed_without_evidence():
    service = AIAssessmentService(FakeLLMClient())
    candidate = _candidate(evidence=[])

    suggestion = service.validate_response(
        response={
            "suggested_verdict": "unknown",
            "evidence_ids": [],
            "evidence_pdf_pages": [],
            "rationale_zh": "输入中没有可支持判断的有效证据。",
            "missing_items_zh": ["实质披露内容"],
            "confidence": 0.7,
        },
        candidate=candidate,
        input_hash="a" * 64,
    )

    assert suggestion.status is AISuggestionStatus.SUCCEEDED
    assert suggestion.suggested_verdict is AssessmentVerdict.UNKNOWN


def test_disclosed_upgrade_from_non_disclosed_rule_requires_human_review():
    service = AIAssessmentService(FakeLLMClient())
    candidate = _candidate()

    suggestion = service.validate_response(
        response={
            "suggested_verdict": "disclosed",
            "evidence_ids": ["evidence-1"],
            "evidence_pdf_pages": [41],
            "rationale_zh": "报告原文直接披露了控制措施。",
            "missing_items_zh": [],
            "confidence": 0.9,
        },
        candidate=candidate,
        input_hash="a" * 64,
    )

    assert suggestion.status is AISuggestionStatus.FAILED
    assert "verdict_upgrade_requires_human_review" in suggestion.guardrail_codes
    assert suggestion.raw_response["suggested_verdict"] == "disclosed"


def test_assess_candidates_enforces_call_budget_and_bounded_concurrency():
    lock = threading.Lock()
    state = {"active": 0, "max_active": 0, "calls": 0}

    class ConcurrentFake(FakeLLMClient):
        def complete_json(self, *, messages, confirm_llm):
            with lock:
                state["active"] += 1
                state["calls"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.03)
            with lock:
                state["active"] -= 1
            return super().complete_json(messages=messages, confirm_llm=confirm_llm)

    candidates = [
        _candidate(
            requirement_id=f"GRI 403-9-{index}",
            evidence=[_evidence(page=41)],
            verdict=AssessmentVerdict.DISCLOSED,
        )
        for index in range(6)
    ]
    service = AIAssessmentService(
        ConcurrentFake(),
        max_concurrency=2,
        max_calls_per_run=4,
    )

    suggestions = service.assess_candidates(candidates, confirm_llm=True)

    assert state["calls"] == 4
    assert 1 < state["max_active"] <= 2
    assert len(suggestions) == 6
    assert [item.status for item in suggestions].count(AISuggestionStatus.SUCCEEDED) == 4
    exhausted = [item for item in suggestions if "call_budget_exhausted" in item.guardrail_codes]
    assert len(exhausted) == 2


def test_assess_candidates_does_not_call_model_without_confirmation():
    client = FakeLLMClient()
    service = AIAssessmentService(client)

    suggestions = service.assess_candidates([_candidate()], confirm_llm=False)

    assert client.calls == []
    assert suggestions[0].status is AISuggestionStatus.SKIPPED
    assert suggestions[0].guardrail_codes == ["external_model_not_confirmed"]


def test_explicit_evaluation_calls_low_priority_and_no_evidence_candidates():
    client = FakeLLMClient(
        response={
            "suggested_verdict": "unknown",
            "evidence_ids": [],
            "evidence_pdf_pages": [],
            "rationale_zh": "输入中没有有效证据。",
            "missing_items_zh": ["实质披露内容"],
            "confidence": 0.7,
        }
    )
    service = AIAssessmentService(client, max_calls_per_run=2)
    candidates = [
        _candidate(requirement_id="GRI 2-1-a", review_priority=RiskLevel.LOW),
        _candidate(requirement_id="GRI 2-1-b", evidence=[]),
    ]

    suggestions = service.assess_explicit_candidates(
        candidates,
        confirm_llm=True,
    )

    assert len(client.calls) == 2
    assert all(item.status is AISuggestionStatus.SUCCEEDED for item in suggestions)
