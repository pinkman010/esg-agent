from dataclasses import dataclass
import re

from src.domain.enums import AssessmentVerdict, PageQualityFlag, ReviewStatus
from src.domain.models import DisclosureAssessment, DisclosureTask, DocumentChunk, EvidenceItem, Recommendation
from src.standards.compilation_guardrails import get_compilation_guardrails
from src.standards.evidence_contracts import get_requirement_contract
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup, evaluate_ontology_verdict
from src.standards.no_evidence_guardrails import get_no_evidence_guardrail
from src.tools.evidence import build_evidence_preview, build_kpi_evidence_preview, chunk_to_evidence
from src.tools.guardrails import build_guarded_assessment
from src.tools.ids import database_safe_id
from src.tools.retrieval import retrieve_evidence


@dataclass(frozen=True)
class DisclosureAgentResult:
    assessment: DisclosureAssessment
    recommendations: list[Recommendation]


class DisclosureAgent:
    def analyze(
        self,
        task: DisclosureTask,
        chunks: list[DocumentChunk],
        confirm_llm: bool,
    ) -> DisclosureAgentResult:
        evidence = self._supplement_requirement_specific_evidence(task, chunks, retrieve_evidence(task, chunks, limit=10))
        evidence = self._filter_invalid_evidence(task, evidence)
        evidence = self._supplement_profile_management_evidence_after_filter(task, chunks, evidence)
        self._mark_requirement_specific_quality_flags(task, evidence)
        self._mark_requirement_specific_previews(task, evidence)
        verdict, rationale, missing_items = self._classify_rule_based(task, evidence)
        assessment = build_guarded_assessment(
            task,
            evidence=evidence,
            model_called=False,
            verdict=verdict,
            rationale=rationale,
            missing_items=missing_items,
        )
        self._apply_profile_route_disclosed_gate(task, assessment)
        self._apply_compilation_guardrails(task, assessment)
        disclosed_not_required_overrides = {
            "GRI 2-7-c-ii",
            "GRI 205-3-b",
            "GRI 302-1-e",
            "GRI 305-1-a",
            "GRI 305-2-a",
            "GRI 305-2-b",
        }
        contract = get_requirement_contract(task.requirement_id)
        if (
            contract is not None
            and contract.review_status is ReviewStatus.NOT_REQUIRED
            and assessment.verdict is AssessmentVerdict.DISCLOSED
        ):
            assessment.review_status = ReviewStatus.NOT_REQUIRED
        elif (
            assessment.verdict is AssessmentVerdict.DISCLOSED
            and any(
                item.metadata.get("ontology_review_status") == ReviewStatus.NOT_REQUIRED.value
                for item in assessment.evidence
            )
        ):
            assessment.review_status = ReviewStatus.NOT_REQUIRED
        elif task.requirement_id in disclosed_not_required_overrides and assessment.verdict is AssessmentVerdict.DISCLOSED:
            assessment.review_status = ReviewStatus.NOT_REQUIRED
        recommendations = self._build_recommendations(task, assessment)
        return DisclosureAgentResult(assessment=assessment, recommendations=recommendations)

    def _apply_compilation_guardrails(self, task: DisclosureTask, assessment: DisclosureAssessment) -> None:
        if assessment.verdict is AssessmentVerdict.DISCLOSED:
            return
        for guardrail in get_compilation_guardrails(task.requirement_id):
            for missing_item in guardrail.missing_item_templates:
                if missing_item not in assessment.missing_items:
                    assessment.missing_items.append(missing_item)

    def _supplement_requirement_specific_evidence(
        self,
        task: DisclosureTask,
        chunks: list[DocumentChunk],
        evidence: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        contract = get_requirement_contract(task.requirement_id)
        is_profile_route = self._uses_report_profile_route(task)
        allowed_pages = set(task.candidate_pages) if is_profile_route and task.candidate_pages else None
        if allowed_pages is None:
            allowed_pages = set(contract.allowed_pages) if contract is not None and contract.allowed_pages else None
        if not allowed_pages:
            allowed_pages = self._requirement_specific_allowed_pages().get(task.requirement_id)
        if not allowed_pages:
            return evidence
        if not evidence and self._uses_report_profile_route(task) and self._should_use_profile_management_candidate(contract):
            return self._profile_candidate_evidence(task, chunks, allowed_pages)
        candidate_pages = set(task.candidate_pages or [])
        if not candidate_pages:
            return evidence

        existing_pages = {item.source_page for item in evidence}
        retrieval_metadata = {
            "retrieval_strategy": "index_page_bounded",
            "candidate_pages": task.candidate_pages,
            "candidate_pdf_pages": task.candidate_pdf_pages,
            "candidate_report_pages": task.candidate_report_pages,
            "candidate_page_source": task.candidate_page_source,
            "index_page": task.index_page,
        }
        supplemented = list(evidence)
        for chunk in chunks:
            if chunk.source_page in existing_pages:
                continue
            if chunk.source_page not in allowed_pages or chunk.source_page not in candidate_pages:
                continue
            supplemented.append(chunk_to_evidence(task, chunk, retrieval_metadata=retrieval_metadata))
            existing_pages.add(chunk.source_page)
        return sorted(supplemented, key=lambda item: item.source_page)

    def _should_use_profile_management_candidate(self, contract) -> bool:
        return bool(contract is not None and EvidenceKind.MANAGEMENT_MECHANISM in contract.evidence_kinds)

    def _profile_candidate_evidence(
        self,
        task: DisclosureTask,
        chunks: list[DocumentChunk],
        allowed_pages: set[int],
    ) -> list[EvidenceItem]:
        candidate_pages = set(task.candidate_pages or [])
        if not candidate_pages:
            return []
        retrieval_metadata = {
            "retrieval_strategy": "index_page_bounded",
            "candidate_pages": task.candidate_pages,
            "candidate_pdf_pages": task.candidate_pdf_pages,
            "candidate_report_pages": task.candidate_report_pages,
            "candidate_page_source": task.candidate_page_source,
            "index_page": task.index_page,
            "profile_candidate_unmatched": True,
        }
        return [
            chunk_to_evidence(task, chunk, retrieval_metadata=retrieval_metadata)
            for chunk in chunks
            if chunk.source_page in allowed_pages and chunk.source_page in candidate_pages
        ]

    def _filter_invalid_evidence(self, task: DisclosureTask, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        evidence = [item for item in evidence if item.metadata.get("retrieval_strategy") != "global_fallback"]
        false_fallback_pages = {23, 60, 64}
        if task.disclosure_id in {"GRI 2-3", "GRI 2-5"}:
            evidence = [
                item
                for item in evidence
                if not (
                    item.metadata.get("retrieval_strategy") == "global_fallback"
                    and item.source_page in false_fallback_pages
                )
            ]
        if task.requirement_id == "GRI 2-7-e":
            return []
        evidence = self._filter_requirement_specific_pages(task, evidence)
        evidence = self._filter_supplier_social_screening_evidence(task, evidence)
        evidence = self._filter_customer_privacy_complaint_evidence(task, evidence)
        self._mark_requirement_specific_quality_flags(task, evidence)
        self._mark_requirement_specific_previews(task, evidence)
        self._mark_omission_note_evidence(task, evidence)
        self._mark_index_statement_evidence(task, evidence)
        if task.requirement_id == "GRI 2-2-c-ii":
            return [item for item in evidence if item.metadata.get("retrieval_strategy") != "global_fallback"]
        if task.requirement_id == "GRI 2-2-c-iii":
            return [item for item in evidence if self._has_2_2_c_iii_sufficient_evidence(item.source_text)]
        return evidence

    def _filter_customer_privacy_complaint_evidence(
        self,
        task: DisclosureTask,
        evidence: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        if task.requirement_id != "GRI 418-1-a":
            return evidence
        return [item for item in evidence if self._has_customer_privacy_complaint_evidence(item.source_text)]

    def _filter_supplier_social_screening_evidence(
        self,
        task: DisclosureTask,
        evidence: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        if task.requirement_id != "GRI 414-1-a":
            return evidence
        social_criteria_terms = (
            "社会责任",
            "社会评价",
            "社会标准",
            "劳动者权益",
            "人权",
            "健康和安全",
            "商业道德",
            "social responsibility",
            "social criteria",
            "labor rights",
            "labour rights",
            "human rights",
            "health and safety",
            "business ethics",
        )
        return [
            item
            for item in evidence
            if any(term in item.source_text.lower() for term in social_criteria_terms)
        ]

    def _supplement_profile_management_evidence_after_filter(
        self,
        task: DisclosureTask,
        chunks: list[DocumentChunk],
        evidence: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        if evidence:
            return evidence
        if not self._uses_report_profile_route(task):
            return evidence
        contract = get_requirement_contract(task.requirement_id)
        if not self._should_use_profile_management_candidate(contract):
            return evidence
        allowed_pages = set(task.candidate_pages or [])
        if not allowed_pages:
            return evidence
        return self._profile_candidate_evidence(task, chunks, allowed_pages)

    def _filter_requirement_specific_pages(
        self,
        task: DisclosureTask,
        evidence: list[EvidenceItem],
    ) -> list[EvidenceItem]:
        guardrail = get_no_evidence_guardrail(task.requirement_id)
        if guardrail is not None:
            return []

        contract = get_requirement_contract(task.requirement_id)
        if contract is not None:
            if contract.verdict is AssessmentVerdict.UNKNOWN and not contract.allowed_pages:
                return []
            filtered = [item for item in evidence if item.source_page not in contract.forbidden_pages]
            if contract.allowed_pages and task.candidate_pages and not self._uses_report_profile_route(task):
                return [item for item in filtered if item.source_page in contract.allowed_pages]
            evidence = filtered

        allowed_pages_by_requirement = self._requirement_specific_allowed_pages()
        requirements_without_valid_evidence = {
            "GRI 2-23-a-iii",
            "GRI 2-23-c",
            "GRI 2-23-d",
            "GRI 2-25-d",
            "GRI 2-26-a-i",
            "GRI 2-27-d",
            "GRI 201-2-a-v",
            "GRI 201-3-a",
            "GRI 201-3-b",
            "GRI 201-3-b-i",
            "GRI 201-3-b-ii",
            "GRI 201-3-b-iii",
            "GRI 201-3-c",
            "GRI 201-3-d",
            "GRI 201-3-e",
            "GRI 202-1-a",
            "GRI 202-1-b",
            "GRI 202-1-c",
            "GRI 202-1-d",
            "GRI 205-2-a",
            "GRI 205-2-d",
            "GRI 205-3-c",
            "GRI 205-3-d",
            "GRI 206-1-b",
            "GRI 207-3-a-i",
            "GRI 207-3-a-ii",
            "GRI 207-3-a-iii",
            "GRI 302-1-b",
            "GRI 302-1-d",
            "GRI 302-1-f",
            "GRI 302-1-g",
            "GRI 302-2-a",
            "GRI 302-2-b",
            "GRI 302-2-c",
            "GRI 302-3-a",
            "GRI 302-3-b",
            "GRI 302-3-c",
            "GRI 302-3-d",
            "GRI 302-4-c",
            "GRI 302-4-d",
            "GRI 302-5-a",
            "GRI 302-5-b",
            "GRI 302-5-c",
            "GRI 303-2-a-i",
            "GRI 303-2-a-iii",
            "GRI 303-2-a-iv",
            "GRI 303-3-a-iii",
            "GRI 303-3-a-iv",
            "GRI 303-3-b-i",
            "GRI 303-3-b-ii",
            "GRI 303-3-b-iii",
            "GRI 303-3-b-iv",
            "GRI 303-3-b-v",
            "GRI 303-3-d",
            "GRI 303-4-a-i",
            "GRI 303-4-a-ii",
            "GRI 303-4-a-iii",
            "GRI 303-4-a-iv",
            "GRI 305-1-d",
            "GRI 305-1-d-i",
            "GRI 305-1-d-ii",
            "GRI 305-1-d-iii",
            "GRI 305-1-f",
            "GRI 305-2-c",
            "GRI 305-2-d",
            "GRI 305-2-d-i",
        }
        if task.requirement_id.startswith("GRI 2-9-c") or task.disclosure_id == "GRI 2-11":
            return []
        if task.requirement_id in requirements_without_valid_evidence:
            return []
        allowed_pages = allowed_pages_by_requirement.get(task.requirement_id)
        if allowed_pages is None:
            return evidence
        if not task.candidate_pages:
            return evidence
        return [item for item in evidence if item.source_page in allowed_pages]

    def _requirement_specific_allowed_pages(self) -> dict[str, set[int]]:
        return {
            "GRI 2-6-b": {4, 6, 52, 53, 54},
            "GRI 2-6-b-i": {4, 6},
            "GRI 2-6-b-ii": {52, 53, 54},
            "GRI 2-6-c": {4, 9, 52, 54},
            "GRI 2-22-a": {4, 5},
            "GRI 2-23-a": {9, 11, 32, 54, 57, 59},
            "GRI 2-23-a-i": {9, 32},
            "GRI 2-23-a-ii": {53, 58},
            "GRI 2-23-a-iv": {32, 54},
            "GRI 2-23-b": {9, 32, 54},
            "GRI 2-23-b-i": {9, 32, 54},
            "GRI 2-23-b-ii": {9, 32, 54},
            "GRI 2-23-e": {32, 54},
            "GRI 2-23-f": {32, 54, 59},
            "GRI 2-24-a": {11, 13, 32, 53, 54, 57, 59},
            "GRI 2-24-a-i": {11, 13, 32, 53, 54, 57, 59},
            "GRI 2-24-a-ii": {11, 13, 32, 53, 54, 57, 59},
            "GRI 2-24-a-iii": {11, 13, 32, 53, 54, 57, 59},
            "GRI 2-24-a-iv": {11, 13, 32, 53, 54, 57, 59},
            "GRI 2-25-a": {32, 53, 59},
            "GRI 2-25-b": {32, 59},
            "GRI 2-25-c": {53, 57, 59},
            "GRI 2-25-e": {56, 58, 59},
            "GRI 2-26-a": {33, 59},
            "GRI 2-26-a-ii": {59},
            "GRI 2-27-a": {72},
            "GRI 2-27-a-i": {72},
            "GRI 2-27-a-ii": {72},
            "GRI 2-27-b": {72},
            "GRI 2-27-b-i": {72},
            "GRI 2-27-b-ii": {72},
            "GRI 2-27-c": {72},
            "GRI 2-28-a": {9},
            "GRI 2-29-a": {14, 15},
            "GRI 2-29-a-i": {14, 15},
            "GRI 2-29-a-ii": {14, 15},
            "GRI 2-29-a-iii": {14, 15},
            "GRI 3-1-a": {14, 15},
            "GRI 3-1-a-i": {14, 15},
            "GRI 3-1-a-ii": {14, 15},
            "GRI 3-1-b": {14, 15},
            "GRI 201-2-a": {17, 18, 19},
            "GRI 201-2-a-i": {17, 18},
            "GRI 201-2-a-ii": {17, 18},
            "GRI 201-2-a-iii": {17, 18},
            "GRI 201-2-a-iv": {17, 18, 19},
            "GRI 203-1-a": {42, 43, 44},
            "GRI 203-1-b": {4, 42, 43, 44},
            "GRI 203-1-c": {42, 43, 44},
            "GRI 203-2-a": {4, 12, 42, 43, 44},
            "GRI 203-2-b": {12, 42, 43, 44, 69},
            "GRI 205-1-a": {58, 68},
            "GRI 205-1-b": {58},
            "GRI 205-2-b": {59, 68},
            "GRI 205-2-c": {54, 58},
            "GRI 205-2-e": {59, 68},
            "GRI 205-3-a": {58, 68},
            "GRI 205-3-b": {68},
            "GRI 206-1-a": {68},
            "GRI 207-1-a": {57},
            "GRI 207-1-a-iii": {57},
            "GRI 207-2-a": {57},
            "GRI 207-2-a-i": {57},
            "GRI 207-2-a-ii": {57},
            "GRI 207-2-a-iii": {57},
            "GRI 207-2-a-iv": {57},
            "GRI 207-3-a": {57},
            "GRI 302-1-a": {63},
            "GRI 302-1-c": {63},
            "GRI 302-1-e": {63},
            "GRI 302-4-a": {23, 63},
            "GRI 302-4-b": {23, 63},
            "GRI 303-1-a": {25, 63},
            "GRI 303-1-b": {25},
            "GRI 303-1-c": {22, 25},
            "GRI 303-1-d": {16, 25},
            "GRI 303-2-a": {22},
            "GRI 303-2-a-ii": {22, 25},
            "GRI 303-3-a": {25, 63},
            "GRI 303-3-a-i": {63},
            "GRI 303-3-a-ii": {63},
            "GRI 303-3-a-v": {63},
            "GRI 303-3-b": {25, 63},
            "GRI 303-3-c": {63},
            "GRI 303-3-c-i": {63},
            "GRI 303-3-c-ii": {63},
            "GRI 303-4-a": {22, 63},
            "GRI 303-4-b": {63},
            "GRI 303-4-b-i": {63},
            "GRI 303-4-b-ii": {63},
            "GRI 305-1-a": {20, 63},
            "GRI 305-1-e": {64},
            "GRI 305-1-g": {64},
            "GRI 305-2-a": {20, 63},
            "GRI 305-2-b": {20, 63},
            "GRI 413-1-a-iv": {14, 42},
        }

    def _mark_requirement_specific_quality_flags(self, task: DisclosureTask, evidence: list[EvidenceItem]) -> None:
        contract = get_requirement_contract(task.requirement_id)
        for item in evidence:
            is_contract_kpi_table_page = contract is not None and item.source_page in contract.kpi_table_pages
            is_profile_kpi_table_page = item.source_page in set(task.kpi_table_pages)
            is_complex_table_page = (
                is_contract_kpi_table_page
                or is_profile_kpi_table_page
                or
                (task.disclosure_id == "GRI 2-7" and item.source_page == 65)
                or (
                    task.disclosure_id in {"GRI 205-1", "GRI 205-2", "GRI 205-3", "GRI 206-1"}
                    and item.source_page == 68
                )
                or (task.disclosure_id.startswith("GRI 302") and item.source_page == 63)
                or (task.disclosure_id.startswith("GRI 303") and item.source_page == 63)
                or (task.disclosure_id.startswith("GRI 305") and item.source_page == 63)
            )
            if is_complex_table_page and PageQualityFlag.COMPLEX_TABLE not in item.quality_flags:
                item.quality_flags.append(PageQualityFlag.COMPLEX_TABLE)
            if is_complex_table_page:
                item.is_kpi_evidence = True
                evidence_kind = (
                    contract.evidence_kinds[0]
                    if contract is not None and contract.evidence_kinds
                    else EvidenceKind.KPI_VALUE
                )
                item.metadata.setdefault("evidence_kind", evidence_kind.value)
                item.evidence_preview = build_kpi_evidence_preview(item.source_text, task.keywords)

    def _mark_requirement_specific_previews(self, task: DisclosureTask, evidence: list[EvidenceItem]) -> None:
        contract = get_requirement_contract(task.requirement_id)
        if contract is None:
            return
        if contract.semantic_group is SemanticGroup.ANTI_CORRUPTION_RISK:
            terms = ["业务单位", "风险程度", "审计策略", "商业道德问题", "反舞弊培训", "反腐败"]
            preview_builder = build_evidence_preview
            window_before = 100
            window_after = 220
        elif (
            contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
            and RequirementFacet.REQUIRES_NEW_SUPPLIER_SCOPE in contract.facets
        ):
            terms = ["供应商社会责任审核", "社会责任审核率", "供应商社会责任", "社会评价"]
            preview_builder = build_kpi_evidence_preview
            window_before = 0
            window_after = 180
        elif (
            contract.semantic_group is SemanticGroup.OHS_KPI
            and RequirementFacet.REQUIRES_COUNT in contract.facets
            and "fatalit" in task.requirement_text.lower()
        ):
            terms = ["员工因工死亡人数", "因工死亡人数", "工伤死亡人数"]
            preview_builder = build_kpi_evidence_preview
            window_before = 0
            window_after = 180
        else:
            return
        for item in evidence:
            item.evidence_preview = preview_builder(
                item.source_text,
                terms,
                window_before=window_before,
                window_after=window_after,
            )

    def _mark_omission_note_evidence(self, task: DisclosureTask, evidence: list[EvidenceItem]) -> None:
        omission_terms = (
            "从略披露",
            "因商业保密限制从略披露",
            "因不适用而从略披露",
            "不适用从略披露",
            "confidentiality constraints",
            "not applicable",
        )
        for item in evidence:
            target_row = self._target_disclosure_row(task.disclosure_id, item.source_text)
            target_row_lower = target_row.lower() if target_row is not None else ""
            if target_row is None or not any(term in target_row or term in target_row_lower for term in omission_terms):
                continue
            item.evidence_preview = target_row
            item.metadata["evidence_type"] = "omission_note"
            if "因商业保密限制从略披露" in target_row or "confidentiality constraints" in target_row_lower:
                item.metadata["omission_reason"] = "confidentiality"
            elif (
                "因不适用而从略披露" in target_row
                or "不适用从略披露" in target_row
                or "not applicable" in target_row_lower
            ):
                item.metadata["omission_reason"] = "not_applicable"

    def _mark_index_statement_evidence(self, task: DisclosureTask, evidence: list[EvidenceItem]) -> None:
        if task.disclosure_id != "GRI 2-27":
            return
        for item in evidence:
            target_row = self._target_disclosure_row(task.disclosure_id, item.source_text)
            if target_row is None or "未发生违法违规事件" not in target_row:
                continue
            item.evidence_preview = target_row
            item.metadata["evidence_type"] = "index_statement"

    def _target_disclosure_row(self, disclosure_id: str, text: str) -> str | None:
        raw_disclosure_id = disclosure_id.removeprefix("GRI ").strip()
        pattern = re.compile(rf"(?<![\d-]){re.escape(raw_disclosure_id)}(?![\d-])")
        lines = text.splitlines()
        for index, line in enumerate(lines):
            match = pattern.search(line)
            if match is None:
                continue
            row_parts = [line[match.start() :]]
            for next_line in lines[index + 1 :]:
                if re.match(r"^\s*(?:\d{1,3}-\d{1,3}|GRI\s+\d+)", next_line.strip()):
                    break
                row_parts.append(next_line)
            return self._before_next_disclosure_token(" ".join(" ".join(row_parts).split()))
        return None

    def _before_next_disclosure_token(self, row: str) -> str:
        match = re.search(r"\s(?:\d{1,3}-\d{1,3}|GRI\s+\d+)\s", row[1:])
        if match is None:
            return row
        return row[: match.start() + 1].strip()

    def _has_2_2_c_iii_sufficient_evidence(self, text: str) -> bool:
        text_lower = text.lower()
        consolidation_terms = {"合并方法", "合并口径", "合并信息", "多实体", "consolidat"}
        difference_terms = {"差异", "不同", "differ", "different"}
        has_consolidation_method = any(term in text_lower for term in consolidation_terms)
        has_difference_explanation = any(term in text_lower for term in difference_terms)
        return has_consolidation_method and has_difference_explanation

    def _uses_report_profile_route(self, task: DisclosureTask) -> bool:
        return bool(task.candidate_page_source and task.candidate_page_source.startswith("report_profile"))

    def _apply_textual_sufficiency_guardrails(self, *, task: DisclosureTask, contract, evidence_text: str, ontology_result):
        evidence_text_lower = evidence_text.lower()
        requirement_text_lower = task.requirement_text.lower()
        if (
            contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
            and RequirementFacet.REQUIRES_PERCENTAGE in contract.facets
            and RequirementFacet.REQUIRES_NEW_SUPPLIER_SCOPE in contract.facets
            and not self._has_new_supplier_screening_percentage_evidence(evidence_text)
            and ("供应商" in evidence_text or "supplier" in evidence_text_lower)
        ):
            return type(ontology_result)(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Supplier assessment evidence is directionally relevant, but it does not confirm the new-supplier screening percentage required by the leaf requirement.",
                missing_items=("新供应商筛选百分比",),
            )
        if (
            contract.semantic_group is SemanticGroup.ZERO_EVENT_COMPLIANCE
            and RequirementFacet.REQUIRES_COUNT in contract.facets
            and self._requires_customer_privacy_complaint_scope(task)
            and not self._has_customer_privacy_complaint_evidence(evidence_text)
        ):
            return type(ontology_result)(
                verdict=AssessmentVerdict.UNKNOWN,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="General product, data security, or privacy management evidence does not directly disclose substantiated customer privacy complaints.",
                missing_items=("客户隐私投诉数量", "投诉来源分类"),
            )
        if (
            contract.semantic_group is SemanticGroup.OHS_KPI
            and RequirementFacet.REQUIRES_COUNT in contract.facets
            and RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in contract.facets
            and self._has_required_ohs_rate_evidence(task, evidence_text)
        ):
            return type(ontology_result)(
                verdict=AssessmentVerdict.DISCLOSED,
                review_status=ReviewStatus.NOT_REQUIRED,
                rationale="OHS KPI evidence directly discloses both the required count and matching rate.",
                missing_items=(),
            )
        return ontology_result

    def _requires_customer_privacy_complaint_scope(self, task: DisclosureTask) -> bool:
        requirement_text_lower = task.requirement_text.lower()
        if task.disclosure_id.startswith("GRI 416") or task.disclosure_id.startswith("GRI 417"):
            return False
        if task.disclosure_id == "GRI 418-1":
            return task.requirement_id in {"GRI 418-1-a", "GRI 418-1-b", "GRI 418-1-c"}
        return (
            "customer privacy" in requirement_text_lower
            or "客户隐私投诉" in task.requirement_text
            or "侵犯客户隐私" in task.requirement_text
        )

    def _has_customer_privacy_complaint_evidence(self, evidence_text: str) -> bool:
        evidence_text_lower = evidence_text.lower()
        has_complaint = "投诉" in evidence_text or "complaint" in evidence_text_lower
        has_customer_privacy = (
            "客户隐私" in evidence_text
            or "侵犯客户隐私" in evidence_text
            or "customer privacy" in evidence_text_lower
        )
        has_data_loss_complaint = "数据丢失" in evidence_text and has_complaint
        return has_complaint and (has_customer_privacy or has_data_loss_complaint)

    def _has_required_ohs_rate_evidence(self, task: DisclosureTask, evidence_text: str) -> bool:
        evidence_text_lower = evidence_text.lower()
        if task.disclosure_id == "GRI 403-10":
            return any(
                term in evidence_text_lower
                for term in (
                    "职业病发病率",
                    "工作相关健康问题发生率",
                    "work-related ill health rate",
                    "occupational disease rate",
                )
            )
        if task.requirement_id.endswith("-a-i") or "fatalit" in task.requirement_text.lower() or "死亡" in task.requirement_text:
            return "死亡率" in evidence_text or "fatality rate" in evidence_text_lower
        return any(term in evidence_text_lower for term in ("trir", "ltir", "百万工时", "per million hours"))

    def _has_new_supplier_screening_percentage_evidence(self, evidence_text: str) -> bool:
        evidence_text_lower = evidence_text.lower()
        direct_patterns = (
            r"新供应商.{0,40}(筛选|评价|评估|审核).{0,40}(百分比|比例|%|％)",
            r"(筛选|评价|评估|审核).{0,40}新供应商.{0,40}(百分比|比例|%|％)",
            r"new suppliers?.{0,80}(screened|screening).{0,80}(percentage|%)",
        )
        return any(re.search(pattern, evidence_text_lower) for pattern in direct_patterns)

    def _apply_profile_route_disclosed_gate(self, task: DisclosureTask, assessment: DisclosureAssessment) -> None:
        if assessment.verdict is not AssessmentVerdict.DISCLOSED:
            return
        if not self._uses_report_profile_route(task):
            return
        if self._has_strong_profile_disclosed_support(task, assessment):
            return
        assessment.verdict = AssessmentVerdict.PARTIALLY_DISCLOSED
        assessment.review_status = ReviewStatus.NEEDS_MANUAL_REVIEW
        assessment.rationale = (
            "Report profile routing found directionally relevant evidence, but the evidence has not passed a leaf-level "
            "sufficiency gate for full disclosure."
        )
        for item in ("leaf-level direct evidence", "人工复核 profile route 证据充分性"):
            if item not in assessment.missing_items:
                assessment.missing_items.append(item)

    def _has_strong_profile_disclosed_support(self, task: DisclosureTask, assessment: DisclosureAssessment) -> bool:
        contract = get_requirement_contract(task.requirement_id)
        evidence_text = "\n".join(item.source_text for item in assessment.evidence)
        if contract is None:
            return False
        if contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT:
            if RequirementFacet.REQUIRES_NEW_SUPPLIER_SCOPE in contract.facets:
                return self._has_new_supplier_screening_percentage_evidence(evidence_text)
            return any(item.metadata.get("ontology_review_status") == ReviewStatus.NOT_REQUIRED.value for item in assessment.evidence)
        if contract.semantic_group is SemanticGroup.ZERO_EVENT_COMPLIANCE and self._requires_customer_privacy_complaint_scope(task):
            return self._has_customer_privacy_complaint_evidence(evidence_text)
        if (
            contract.semantic_group is SemanticGroup.OHS_KPI
            and RequirementFacet.REQUIRES_COUNT in contract.facets
            and RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in contract.facets
        ):
            return self._has_required_ohs_rate_evidence(task, evidence_text)
        return any(item.metadata.get("ontology_review_status") == ReviewStatus.NOT_REQUIRED.value for item in assessment.evidence)

    def _classify_rule_based(
        self,
        task: DisclosureTask,
        evidence: list[EvidenceItem],
    ) -> tuple[AssessmentVerdict | None, str | None, list[str]]:
        bounded_evidence = [item for item in evidence if item.metadata.get("retrieval_strategy") == "index_page_bounded"]
        guardrail = get_no_evidence_guardrail(task.requirement_id)
        if guardrail is not None and not bounded_evidence:
            return (
                AssessmentVerdict.UNKNOWN,
                guardrail.rationale,
                list(guardrail.missing_items),
            )
        if task.requirement_id == "GRI 2-2-c-ii" and not bounded_evidence:
            return (
                AssessmentVerdict.UNKNOWN,
                "No valid report evidence explains how mergers, acquisitions, or entity disposals affect consolidation.",
                ["并购、收购和实体处置处理方式"],
            )
        if task.requirement_id == "GRI 2-2-c-iii" and not bounded_evidence:
            return (
                AssessmentVerdict.UNKNOWN,
                "No valid report evidence explains whether or how the consolidation approach differs across disclosures.",
                ["多实体信息合并方法", "合并方法差异说明"],
            )
        if task.requirement_id == "GRI 418-1-a" and not bounded_evidence:
            return (
                AssessmentVerdict.UNKNOWN,
                "报告未披露经证实的客户隐私投诉总数，也未分别披露外部方投诉和监管机构投诉数量；当前无有效 source evidence，因此判定为 unknown。",
                [
                    "经证实的客户隐私投诉总数",
                    "由外部方提出并经组织证实的投诉数量",
                    "监管机构提出的投诉数量",
                ],
            )
        if not bounded_evidence:
            return None, None, []

        evidence_text = "\n".join(item.source_text for item in bounded_evidence)
        evidence_text_lower = evidence_text.lower()
        if any(item.metadata.get("evidence_type") == "omission_note" for item in evidence):
            return (
                AssessmentVerdict.UNKNOWN,
                "The report index contains an omission note, but no substantive disclosure evidence was found.",
                ["实质披露内容", "从略披露原因对应的人工复核"],
            )

        contract = get_requirement_contract(task.requirement_id)
        if contract is not None and contract.verdict is not None:
            for item in evidence:
                item.metadata.setdefault("decision_source", "contract_explicit_verdict")
            return (
                contract.verdict,
                contract.rationale,
                list(contract.missing_items),
            )
        if (
            contract is not None
            and contract.semantic_group is not None
            and contract.facets
            and contract.evidence_kinds
        ):
            ontology_result = evaluate_ontology_verdict(
                semantic_group=contract.semantic_group,
                facets=contract.facets,
                evidence_kinds=contract.evidence_kinds,
            )
            ontology_result = self._apply_textual_sufficiency_guardrails(
                task=task,
                contract=contract,
                evidence_text=evidence_text,
                ontology_result=ontology_result,
            )
            decision_source = "contract_guardrail+ontology_matrix" if contract.missing_items else "ontology_matrix"
            for item in evidence:
                item.metadata.setdefault("decision_source", decision_source)
                item.metadata.setdefault("ontology_review_status", ontology_result.review_status.value)
            if contract.rationale:
                rationale = contract.rationale
                missing_items = list(contract.missing_items)
            else:
                rationale = ontology_result.rationale
                missing_items = [*ontology_result.missing_items]
                for item in contract.missing_items:
                    if item not in missing_items:
                        missing_items.append(item)
            return (
                ontology_result.verdict,
                rationale,
                missing_items,
            )

        if task.requirement_id == "GRI 2-26-a-ii":
            return (
                AssessmentVerdict.DISCLOSED,
                "Bounded evidence discloses channels for raising concerns about business conduct.",
                [],
            )

        index_statement_items = {
            "GRI 2-27-a",
            "GRI 2-27-a-i",
            "GRI 2-27-a-ii",
            "GRI 2-27-b",
            "GRI 2-27-b-i",
            "GRI 2-27-b-ii",
            "GRI 2-27-c",
        }
        if task.requirement_id in index_statement_items and any(
            item.metadata.get("evidence_type") == "index_statement" for item in evidence
        ):
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "The GRI index states that no violations occurred during the reporting period, but it does not provide full substantive detail for this sub-requirement.",
                ["实质性违法违规事件口径", "罚款或处罚明细的完整说明"],
            )

        current_150_partial_items = {
            "GRI 2-22-a",
            "GRI 2-23-a",
            "GRI 2-23-a-i",
            "GRI 2-23-a-ii",
            "GRI 2-23-a-iv",
            "GRI 2-23-b",
            "GRI 2-23-b-i",
            "GRI 2-23-b-ii",
            "GRI 2-23-e",
            "GRI 2-23-f",
            "GRI 2-24-a",
            "GRI 2-24-a-i",
            "GRI 2-24-a-ii",
            "GRI 2-24-a-iii",
            "GRI 2-24-a-iv",
            "GRI 2-25-a",
            "GRI 2-25-b",
            "GRI 2-25-c",
            "GRI 2-25-e",
            "GRI 2-26-a",
            "GRI 2-28-a",
            "GRI 2-29-a",
            "GRI 2-29-a-i",
            "GRI 2-29-a-ii",
            "GRI 2-29-a-iii",
            "GRI 3-1-a",
            "GRI 3-1-a-i",
            "GRI 3-1-a-ii",
            "GRI 3-1-b",
        }
        if task.requirement_id in current_150_partial_items:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence provides directionally relevant disclosure, but it does not fully satisfy this GRI requirement.",
                ["完整披露口径", "人工复核充分性"],
            )

        climate_disclosed_items = {
            "GRI 201-2-a-i",
            "GRI 201-2-a-ii",
            "GRI 201-2-a-iv",
        }
        if task.requirement_id in climate_disclosed_items:
            return (
                AssessmentVerdict.DISCLOSED,
                "Bounded evidence discloses the relevant climate-related risks, opportunities, impacts, or management approach for this sub-requirement.",
                [],
            )

        climate_partial_items = {
            "GRI 201-2-a",
            "GRI 201-2-a-iii",
        }
        if task.requirement_id in climate_partial_items:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence describes climate-related risks, opportunities, and qualitative financial implications, but it does not fully quantify financial impacts or assumptions.",
                ["量化财务影响", "估算假设或方法"],
            )

        indirect_economic_impact_items = {
            "GRI 203-1-a",
            "GRI 203-1-b",
            "GRI 203-1-c",
            "GRI 203-2-a",
            "GRI 203-2-b",
        }
        if task.requirement_id in indirect_economic_impact_items:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence provides community, infrastructure, service, or indirect-economic-impact examples, but it does not fully disclose scope, beneficiaries, impact assessment, or service nature.",
                ["投资范围和规模", "受益人群", "影响评估", "服务性质"],
            )

        if task.requirement_id == "GRI 205-3-b":
            return (
                AssessmentVerdict.DISCLOSED,
                "Bounded KPI evidence directly discloses incidents in which employees were dismissed or disciplined for corruption.",
                [],
            )

        anti_corruption_partial_items = {
            "GRI 205-1-a",
            "GRI 205-1-b",
            "GRI 205-2-b",
            "GRI 205-2-c",
            "GRI 205-2-e",
            "GRI 205-3-a",
        }
        if task.requirement_id in anti_corruption_partial_items:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence describes anti-corruption risk assessment, communication, training, or KPI directionally, but it does not provide all GRI-required totals, percentages, categories, regions, or incident nature.",
                ["总数和百分比", "类别或地区拆分", "事件性质或完整口径"],
            )

        if task.requirement_id == "GRI 206-1-a":
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded KPI evidence discloses anti-competitive behavior incident count, but it does not clearly establish pending or completed legal actions under anti-competitive, anti-trust, or monopoly practices.",
                ["反竞争相关法律诉讼口径", "待决或已完成法律行动"],
            )

        tax_partial_items = {
            "GRI 207-1-a",
            "GRI 207-1-a-iii",
            "GRI 207-2-a",
            "GRI 207-2-a-i",
            "GRI 207-2-a-ii",
            "GRI 207-2-a-iii",
            "GRI 207-2-a-iv",
            "GRI 207-3-a",
        }
        if task.requirement_id in tax_partial_items:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence describes tax governance, financial compliance, tax risk management, or tax-related stakeholder expectations, but it does not fully disclose the complete GRI tax governance or stakeholder engagement process.",
                ["完整税务战略或治理框架", "正式责任主体和评估机制", "税务相关利益相关方参与流程"],
            )

        if task.requirement_id in {"GRI 302-1-a", "GRI 302-1-c"}:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded KPI evidence discloses energy consumption figures, but it does not fully establish all GRI 302-1 unit, fuel-type, heating, cooling, steam, and methodology requirements.",
                ["完整能源类型和单位口径", "热力、制冷、蒸汽要素", "编制方法人工复核"],
            )

        if task.requirement_id == "GRI 302-1-e":
            return (
                AssessmentVerdict.DISCLOSED,
                "Bounded KPI evidence directly discloses total energy consumption inside the organization.",
                [],
            )

        if task.requirement_id in {"GRI 302-4-a", "GRI 302-4-b"}:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence discloses electricity-saving reductions, but it does not fully disclose all energy types, baseline, methods, assumptions, or calculation tools required by GRI 302-4.",
                ["完整能源类型", "节能量计算基准", "计算方法、假设或工具"],
            )

        water_partial_items = {
            "GRI 303-1-a",
            "GRI 303-1-b",
            "GRI 303-1-c",
            "GRI 303-1-d",
            "GRI 303-2-a",
            "GRI 303-2-a-ii",
            "GRI 303-3-a",
            "GRI 303-3-a-i",
            "GRI 303-3-a-ii",
            "GRI 303-3-a-v",
            "GRI 303-3-b",
            "GRI 303-3-c",
            "GRI 303-3-c-i",
            "GRI 303-3-c-ii",
            "GRI 303-4-a",
            "GRI 303-4-b",
            "GRI 303-4-b-i",
            "GRI 303-4-b-ii",
        }
        if task.requirement_id in water_partial_items:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence provides water management, withdrawal, or discharge figures directionally, but it does not fully disclose all GRI-required source, destination, stress-area, standard, method, and compilation details.",
                ["完整水源或排放目的地拆分", "高水风险区域拆分", "内部标准或方法说明", "数据编制方法"],
            )

        ghg_disclosed_items = {
            "GRI 305-1-a",
            "GRI 305-2-a",
            "GRI 305-2-b",
        }
        if task.requirement_id in ghg_disclosed_items:
            return (
                AssessmentVerdict.DISCLOSED,
                "Bounded evidence directly discloses the relevant Scope 1 or Scope 2 GHG emissions figure.",
                [],
            )

        if task.requirement_id in {"GRI 305-1-e", "GRI 305-1-g"}:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence describes GHG calculation methods, emission factors, or standards, but it does not fully disclose all GRI-required gases, factor sources, GWP rates, and methodology details.",
                ["温室气体种类", "排放因子来源", "全球变暖潜势来源", "完整核算标准或方法"],
            )

        if task.requirement_id == "GRI 2-3-a":
            period_terms = {"报告期", "2024年1月1日", "2024 年 1 月 1 日", "2024-01-01"}
            frequency_terms = {"报告频率", "报告周期", "年度报告", "每年", "annual"}
            has_reporting_period = any(term in evidence_text_lower for term in period_terms)
            has_reporting_frequency = any(term in evidence_text_lower for term in frequency_terms)
            if has_reporting_period and not has_reporting_frequency:
                return (
                    AssessmentVerdict.PARTIALLY_DISCLOSED,
                    "Bounded evidence discloses the reporting period, but it does not disclose reporting frequency.",
                    ["报告频率"],
                )

        if task.requirement_id == "GRI 2-5-a":
            assurance_terms = {"鉴证报告", "独立有限鉴证", "有限保证", "external assurance"}
            assurance_policy_terms = {"鉴证政策", "外部鉴证政策", "治理机构", "高管", "最高治理机构"}
            has_assurance_practice = any(term in evidence_text_lower for term in assurance_terms)
            has_assurance_policy = any(term in evidence_text_lower for term in assurance_policy_terms)
            if has_assurance_practice and not has_assurance_policy:
                return (
                    AssessmentVerdict.PARTIALLY_DISCLOSED,
                    "Bounded evidence shows external assurance practice, but it does not describe the assurance policy or governance involvement.",
                    ["外部鉴证政策", "治理机构和高管参与说明"],
                )

        if task.requirement_id in {"GRI 2-6-b", "GRI 2-6-b-i", "GRI 2-6-b-ii", "GRI 2-6-c"}:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence describes parts of activities, products, services, markets, value chain, or business relationships, but it is not complete enough for full GRI 2-6 disclosure.",
                ["完整活动、产品、服务和服务市场说明", "完整价值链和业务关系说明"],
            )

        if task.requirement_id == "GRI 2-6-d":
            return (
                AssessmentVerdict.UNKNOWN,
                "No valid report evidence discloses significant changes in activities, value chain, or business relationships compared with the previous reporting period.",
                ["活动、价值链和业务关系较上一报告期的重大变化"],
            )

        if task.requirement_id == "GRI 2-7-c":
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence discloses employee composition at reporting period end, but it does not explain head count, FTE, or complete assumptions used to compile employee data.",
                ["head count 或 FTE 口径", "员工数据编制假设"],
            )

        if task.requirement_id in {"GRI 2-7-d", "GRI 2-7-e"}:
            missing = (
                ["理解员工数据所需的背景信息"]
                if task.requirement_id == "GRI 2-7-d"
                else ["报告期内或报告期间之间员工人数重大波动说明"]
            )
            return (
                AssessmentVerdict.UNKNOWN,
                "Bounded evidence does not provide sufficient context for employee data or significant employee-number fluctuations.",
                missing,
            )

        if task.disclosure_id == "GRI 2-8":
            return (
                AssessmentVerdict.UNKNOWN,
                "Report evidence about ordinary employees, suppliers, or contractor safety cannot substitute for non-employee worker count, types, or contract relationship disclosure.",
                ["非雇员工作者总数", "非雇员工作者类型", "合同关系和统计方法"],
            )

        allowed_governance_impact_items = {
            "GRI 2-9-a",
            "GRI 2-9-b",
            "GRI 2-12-a",
            "GRI 2-12-b",
            "GRI 2-12-b-i",
            "GRI 2-12-b-ii",
            "GRI 2-12-c",
            "GRI 2-13-a",
            "GRI 2-13-a-i",
            "GRI 2-13-a-ii",
            "GRI 2-13-b",
        }
        if task.requirement_id in allowed_governance_impact_items:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence describes ESG governance bodies, responsibilities, and reporting lines, but it does not fully establish the highest-governance-body mandate or complete impact-management process.",
                ["最高治理机构委员会体系", "最高治理机构正式授权", "完整影响管理流程和充分性说明"],
            )

        if task.requirement_id == "GRI 2-1-b":
            ownership_or_form_terms = {"所有权性质", "法律形式", "股权结构", "民营", "国有", "ownership", "legal form"}
            if not any(term in evidence_text_lower for term in ownership_or_form_terms):
                return (
                    AssessmentVerdict.UNKNOWN,
                    "Company-name text does not disclose ownership nature or legal form.",
                    ["所有权性质", "法律形式"],
                )

        if task.requirement_id == "GRI 2-1-c":
            formal_headquarters_terms = {"总部地址", "总部所在地", "总部位于", "注册地址", "headquarters located"}
            if "总部" in evidence_text and not any(term in evidence_text_lower for term in formal_headquarters_terms):
                return (
                    AssessmentVerdict.PARTIALLY_DISCLOSED,
                    "Bounded evidence references a headquarters building, but it does not provide a formal headquarters location or address.",
                    ["正式总部所在地或地址"],
                )

        if task.requirement_id == "GRI 2-1-d":
            operation_scope_terms = {"全球", "海外订单", "全球项目", "全球市场", "亚太"}
            country_list_terms = {"运营国家", "国家清单", "countries of operation"}
            if any(term in evidence_text_lower for term in operation_scope_terms) and not any(
                term in evidence_text_lower for term in country_list_terms
            ):
                return (
                    AssessmentVerdict.PARTIALLY_DISCLOSED,
                    "Bounded evidence describes global or regional operations, but it does not list countries of operation.",
                    ["运营国家清单"],
                )

        if task.requirement_id == "GRI 2-2-c":
            boundary_terms = {"报告边界", "实际运营场所", "报告范围"}
            consolidation_terms = {"合并方法", "合并口径", "少数权益", "并购", "收购", "处置"}
            if any(term in evidence_text for term in boundary_terms) and not any(term in evidence_text for term in consolidation_terms):
                return (
                    AssessmentVerdict.PARTIALLY_DISCLOSED,
                    "Bounded evidence describes the report boundary, but it does not explain the consolidation approach for multi-entity information.",
                    ["多实体信息合并方法", "少数权益调整说明", "并购、收购和实体处置处理方式", "不同披露项差异说明"],
                )

        if task.requirement_id == "GRI 2-2-c-iii":
            if not self._has_2_2_c_iii_sufficient_evidence(evidence_text_lower):
                return (
                    AssessmentVerdict.UNKNOWN,
                    "Bounded evidence does not explain whether or how the consolidation approach differs across disclosures.",
                    ["多实体信息合并方法", "合并方法差异说明"],
                )

        if task.requirement_id != "GRI 2-2-a":
            return None, None, []

        boundary_terms = {"报告边界", "实际运营场所", "统计口径", "合并范围", "纳入报告"}
        entity_list_terms = {"实体清单", "实体列表", "全部实体", "所有实体", "合并报表实体"}
        has_boundary_evidence = any(term in evidence_text for term in boundary_terms)
        has_entity_list_evidence = any(term in evidence_text for term in entity_list_terms)
        if has_boundary_evidence and not has_entity_list_evidence:
            return (
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "Bounded evidence describes the reporting boundary, but it does not provide a complete entity list.",
                ["完整实体清单", "纳入可持续发展报告的全部实体"],
            )

        return None, None, []

    def _build_recommendations(self, task: DisclosureTask, assessment: DisclosureAssessment) -> list[Recommendation]:
        if assessment.verdict is AssessmentVerdict.DISCLOSED:
            return []
        return [
            Recommendation(
                recommendation_id=database_safe_id(f"recommendation:{task.task_id}", "recommendation"),
                run_id=task.run_id,
                report_id=task.report_id,
                disclosure_id=task.disclosure_id,
                requirement_id=task.requirement_id,
                recommendation_text=f"Add report evidence for requirement {task.requirement_id}.",
            )
        ]
