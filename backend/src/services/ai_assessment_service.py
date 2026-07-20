import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from uuid import uuid4

from pydantic import ValidationError

from src.domain.ai_models import AIAssessmentResponse, AIAssessmentSuggestion
from src.domain.enums import AISuggestionStatus, AssessmentVerdict, RiskLevel
from src.domain.models import DisclosureAssessment, DisclosureTask, EvidenceItem
from src.tools.llm_client import LLMClient, LLMCompletionError, LLMCompletionResult


NON_SUBSTANTIVE_EVIDENCE_TYPES = frozenset(
    {"omission_note", "index_statement", "chapter_cover", "candidate_page"}
)
INDEPENDENT_STRUCTURE_STATUSES = frozenset({"verified", "normalized"})
AI_REVIEW_PRIORITIES = frozenset({RiskLevel.HIGH, RiskLevel.MEDIUM})
PRIORITY_ORDER = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
MAX_EVIDENCE_ITEMS = 5
MAX_EVIDENCE_TEXT_CHARS = 1200


SYSTEM_MESSAGE = """你是 ESG 披露分析辅助工具。请严格遵守以下约束：
1. 仅判断当前单条 requirement，并输出纯 JSON，不得输出 Markdown 或额外说明。
2. 只能引用输入中提供的 evidence_id；不得补充、猜测或发明证据和页码。
3. 索引、从略说明、章节封面和候选页不能单独支撑 disclosed。
4. 没有有效实质证据时，只能建议 unknown。
5. partially_disclosed 必须至少给出一个 missing_items_zh。
6. 不得判断适用性、风险优先级、人工复核状态和合规认证。
7. rationale_zh 只能用中文陈述输入证据能够支持的事实。
JSON 输出示例：
{"suggested_verdict":"partially_disclosed","evidence_ids":["evidence-1"],"evidence_pdf_pages":[41],"rationale_zh":"报告披露了部分要求内容。","missing_items_zh":["尚缺少的要求内容"],"confidence":0.8}
"""


@dataclass(frozen=True)
class AIAssessmentCandidate:
    task: DisclosureTask
    assessment: DisclosureAssessment
    review_priority: RiskLevel


class AIAssessmentService:
    def __init__(
        self,
        llm_client: LLMClient,
        *,
        provider: str = "deepseek",
        prompt_version: str = "deepseek-gri-assist-v1",
        max_concurrency: int = 8,
        max_calls_per_run: int = 200,
    ) -> None:
        if not 1 <= max_concurrency <= 16:
            raise ValueError("max_concurrency must be between 1 and 16")
        if max_calls_per_run < 1:
            raise ValueError("max_calls_per_run must be positive")
        self.llm_client = llm_client
        self.provider = provider
        self.prompt_version = prompt_version
        self.max_concurrency = max_concurrency
        self.max_calls_per_run = max_calls_per_run

    def should_call(self, candidate: AIAssessmentCandidate) -> bool:
        if candidate.task.structure_status not in INDEPENDENT_STRUCTURE_STATUSES:
            return False
        if candidate.review_priority not in AI_REVIEW_PRIORITIES:
            return False
        return any(self._is_substantive(item) for item in candidate.assessment.evidence)

    def build_messages(
        self,
        candidate: AIAssessmentCandidate,
    ) -> tuple[list[dict[str, str]], str]:
        evidence_payload = [
            {
                "evidence_id": item.evidence_id,
                "source_pdf_page": item.source_pdf_page or item.source_page,
                "evidence_type": self._evidence_type(item),
                "quality_flags": [flag.value for flag in item.quality_flags],
                "source_text": item.source_text[:MAX_EVIDENCE_TEXT_CHARS],
            }
            for item in self._prompt_evidence(candidate)
        ]
        payload = {
            "requirement_id": candidate.task.requirement_id,
            "effective_requirement_text": candidate.task.requirement_text,
            "source_requirement_text": candidate.task.source_requirement_text,
            "context_requirement_ids": candidate.task.context_requirement_ids,
            "rule_verdict": candidate.assessment.verdict.value,
            "evidence": evidence_payload,
            "required_json_output": {
                "suggested_verdict": "disclosed|partially_disclosed|unknown",
                "evidence_ids": [],
                "evidence_pdf_pages": [],
                "rationale_zh": "",
                "missing_items_zh": [],
                "confidence": 0.0,
            },
        }
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE.strip()},
            {
                "role": "user",
                "content": json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
        ]
        canonical = json.dumps(
            messages,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        input_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return messages, input_hash

    def validate_response(
        self,
        *,
        response: dict,
        candidate: AIAssessmentCandidate,
        input_hash: str,
        completion: LLMCompletionResult | None = None,
    ) -> AIAssessmentSuggestion:
        try:
            parsed = AIAssessmentResponse.model_validate(response)
        except ValidationError:
            return self._failed_suggestion(
                candidate,
                input_hash=input_hash,
                guardrail_codes=["response_schema_invalid"],
                error_code="ai_response_validation_failed",
                raw_response=response,
                completion=completion,
            )

        allowed_evidence = {
            item.evidence_id: item for item in self._prompt_evidence(candidate)
        }
        guardrail_codes: list[str] = []
        if len(parsed.evidence_ids) != len(parsed.evidence_pdf_pages):
            guardrail_codes.append("evidence_page_cardinality_mismatch")
        if len(set(parsed.evidence_ids)) != len(parsed.evidence_ids):
            guardrail_codes.append("duplicate_evidence_reference")

        cited_items: list[EvidenceItem] = []
        for index, evidence_id in enumerate(parsed.evidence_ids):
            evidence = allowed_evidence.get(evidence_id)
            if evidence is None:
                guardrail_codes.append("evidence_reference_out_of_scope")
                continue
            cited_items.append(evidence)
            if index < len(parsed.evidence_pdf_pages):
                expected_page = evidence.source_pdf_page or evidence.source_page
                if parsed.evidence_pdf_pages[index] != expected_page:
                    guardrail_codes.append("evidence_page_mismatch")

        if parsed.suggested_verdict == AssessmentVerdict.DISCLOSED.value and not any(
            self._is_substantive(item) for item in cited_items
        ):
            guardrail_codes.append("disclosed_without_substantive_evidence")
        if (
            parsed.suggested_verdict == AssessmentVerdict.PARTIALLY_DISCLOSED.value
            and not parsed.missing_items_zh
        ):
            guardrail_codes.append("partial_without_missing_items")

        guardrail_codes = list(dict.fromkeys(guardrail_codes))
        if guardrail_codes:
            return self._failed_suggestion(
                candidate,
                input_hash=input_hash,
                guardrail_codes=guardrail_codes,
                error_code="ai_response_guardrail_failed",
                raw_response=response,
                completion=completion,
                parsed=parsed,
            )

        return self._suggestion_from_response(
            candidate,
            parsed,
            input_hash=input_hash,
            status=AISuggestionStatus.SUCCEEDED,
            raw_response=response,
            completion=completion,
        )

    def assess_candidates(
        self,
        candidates: list[AIAssessmentCandidate],
        *,
        confirm_llm: bool,
    ) -> list[AIAssessmentSuggestion]:
        ordered = sorted(
            candidates,
            key=lambda item: (
                PRIORITY_ORDER[item.review_priority],
                item.task.requirement_id,
            ),
        )
        results: list[AIAssessmentSuggestion | None] = [None] * len(ordered)
        callable_items: list[tuple[int, AIAssessmentCandidate]] = []

        for index, candidate in enumerate(ordered):
            if not confirm_llm:
                results[index] = self._skipped_suggestion(
                    candidate, "external_model_not_confirmed"
                )
            elif not self.should_call(candidate):
                results[index] = self._skipped_suggestion(
                    candidate, self._skip_code(candidate)
                )
            else:
                callable_items.append((index, candidate))

        budgeted = callable_items[: self.max_calls_per_run]
        for index, candidate in callable_items[self.max_calls_per_run :]:
            results[index] = self._skipped_suggestion(candidate, "call_budget_exhausted")

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            future_map = {
                executor.submit(self._assess_one, candidate): index
                for index, candidate in budgeted
            }
            for future in as_completed(future_map):
                results[future_map[future]] = future.result()

        return [result for result in results if result is not None]

    def _assess_one(self, candidate: AIAssessmentCandidate) -> AIAssessmentSuggestion:
        messages, input_hash = self.build_messages(candidate)
        try:
            completion = self.llm_client.complete_json(
                messages=messages,
                confirm_llm=True,
            )
        except LLMCompletionError as exc:
            return self._failed_suggestion(
                candidate,
                input_hash=input_hash,
                guardrail_codes=[exc.error_code],
                error_code=exc.error_code,
                retry_count=exc.retry_count,
            )
        except Exception:
            return self._failed_suggestion(
                candidate,
                input_hash=input_hash,
                guardrail_codes=["ai_service_unexpected_error"],
                error_code="ai_service_unexpected_error",
            )
        return self.validate_response(
            response=completion.content,
            candidate=candidate,
            input_hash=input_hash,
            completion=completion,
        )

    def _failed_suggestion(
        self,
        candidate: AIAssessmentCandidate,
        *,
        input_hash: str,
        guardrail_codes: list[str],
        error_code: str,
        raw_response: dict | None = None,
        completion: LLMCompletionResult | None = None,
        parsed: AIAssessmentResponse | None = None,
        retry_count: int = 0,
    ) -> AIAssessmentSuggestion:
        if parsed is not None:
            return self._suggestion_from_response(
                candidate,
                parsed,
                input_hash=input_hash,
                status=AISuggestionStatus.FAILED,
                raw_response=raw_response,
                completion=completion,
                guardrail_codes=guardrail_codes,
                error_code=error_code,
            )
        return AIAssessmentSuggestion(
            suggestion_id=f"ai-suggestion-{uuid4().hex}",
            assessment_id=candidate.assessment.assessment_id,
            run_id=candidate.assessment.run_id,
            status=AISuggestionStatus.FAILED,
            provider=self.provider,
            model=self.llm_client.model,
            prompt_version=self.prompt_version,
            input_hash=input_hash,
            guardrail_codes=guardrail_codes,
            retry_count=completion.retry_count if completion else retry_count,
            usage=completion.usage if completion else {},
            finish_reason=completion.finish_reason if completion else None,
            latency_ms=completion.latency_ms if completion else None,
            error_code=error_code,
            error_message="AI suggestion could not pass validation",
            raw_response=raw_response,
        )

    def _suggestion_from_response(
        self,
        candidate: AIAssessmentCandidate,
        parsed: AIAssessmentResponse,
        *,
        input_hash: str,
        status: AISuggestionStatus,
        raw_response: dict | None,
        completion: LLMCompletionResult | None,
        guardrail_codes: list[str] | None = None,
        error_code: str | None = None,
    ) -> AIAssessmentSuggestion:
        return AIAssessmentSuggestion(
            suggestion_id=f"ai-suggestion-{uuid4().hex}",
            assessment_id=candidate.assessment.assessment_id,
            run_id=candidate.assessment.run_id,
            status=status,
            provider=self.provider,
            model=completion.model if completion else self.llm_client.model,
            prompt_version=self.prompt_version,
            input_hash=input_hash,
            suggested_verdict=AssessmentVerdict(parsed.suggested_verdict),
            rationale_zh=parsed.rationale_zh,
            missing_items_zh=parsed.missing_items_zh,
            evidence_ids=parsed.evidence_ids,
            evidence_pdf_pages=parsed.evidence_pdf_pages,
            confidence=parsed.confidence,
            guardrail_codes=guardrail_codes or [],
            usage=completion.usage if completion else {},
            finish_reason=completion.finish_reason if completion else None,
            latency_ms=completion.latency_ms if completion else None,
            retry_count=completion.retry_count if completion else 0,
            error_code=error_code,
            error_message=(
                "AI suggestion did not pass evidence guardrails"
                if error_code
                else None
            ),
            raw_response=raw_response,
        )

    def _skipped_suggestion(
        self,
        candidate: AIAssessmentCandidate,
        guardrail_code: str,
    ) -> AIAssessmentSuggestion:
        _, input_hash = self.build_messages(candidate)
        return AIAssessmentSuggestion(
            suggestion_id=f"ai-suggestion-{uuid4().hex}",
            assessment_id=candidate.assessment.assessment_id,
            run_id=candidate.assessment.run_id,
            status=AISuggestionStatus.SKIPPED,
            provider=self.provider,
            model=self.llm_client.model,
            prompt_version=self.prompt_version,
            input_hash=input_hash,
            guardrail_codes=[guardrail_code],
            error_code=guardrail_code,
        )

    @staticmethod
    def _prompt_evidence(candidate: AIAssessmentCandidate) -> list[EvidenceItem]:
        return candidate.assessment.evidence[:MAX_EVIDENCE_ITEMS]

    @staticmethod
    def _evidence_type(evidence: EvidenceItem) -> str:
        return str(evidence.metadata.get("evidence_type", "substantive_report_evidence"))

    @classmethod
    def _is_substantive(cls, evidence: EvidenceItem) -> bool:
        return cls._evidence_type(evidence) not in NON_SUBSTANTIVE_EVIDENCE_TYPES

    @staticmethod
    def _skip_code(candidate: AIAssessmentCandidate) -> str:
        if candidate.task.structure_status not in INDEPENDENT_STRUCTURE_STATUSES:
            return "structure_not_independent"
        if candidate.review_priority is RiskLevel.LOW:
            return "low_review_priority"
        return "no_substantive_evidence"
