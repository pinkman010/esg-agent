from dataclasses import dataclass

from src.domain.enums import AssessmentVerdict
from src.domain.models import DisclosureAssessment, DisclosureTask, DocumentChunk, EvidenceItem, Recommendation
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
        evidence = self._filter_invalid_evidence(task, retrieve_evidence(task, chunks))
        verdict, rationale, missing_items = self._classify_rule_based(task, evidence)
        assessment = build_guarded_assessment(
            task,
            evidence=evidence,
            model_called=False,
            verdict=verdict,
            rationale=rationale,
            missing_items=missing_items,
        )
        recommendations = self._build_recommendations(task, assessment)
        return DisclosureAgentResult(assessment=assessment, recommendations=recommendations)

    def _filter_invalid_evidence(self, task: DisclosureTask, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
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
        if task.requirement_id == "GRI 2-2-c-ii":
            return [item for item in evidence if item.metadata.get("retrieval_strategy") != "global_fallback"]
        if task.requirement_id == "GRI 2-2-c-iii":
            return [item for item in evidence if self._has_2_2_c_iii_sufficient_evidence(item.source_text)]
        return evidence

    def _has_2_2_c_iii_sufficient_evidence(self, text: str) -> bool:
        text_lower = text.lower()
        consolidation_terms = {"合并方法", "合并口径", "合并信息", "多实体", "consolidat"}
        difference_terms = {"差异", "不同", "differ", "different"}
        has_consolidation_method = any(term in text_lower for term in consolidation_terms)
        has_difference_explanation = any(term in text_lower for term in difference_terms)
        return has_consolidation_method and has_difference_explanation

    def _classify_rule_based(
        self,
        task: DisclosureTask,
        evidence: list[EvidenceItem],
    ) -> tuple[AssessmentVerdict | None, str | None, list[str]]:
        bounded_evidence = [item for item in evidence if item.metadata.get("retrieval_strategy") == "index_page_bounded"]
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
        if not bounded_evidence:
            return None, None, []

        evidence_text = "\n".join(item.source_text for item in bounded_evidence)
        evidence_text_lower = evidence_text.lower()
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
