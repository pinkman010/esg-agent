from __future__ import annotations

from dataclasses import dataclass
import re

from src.domain.enums import AssessmentVerdict
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup


@dataclass(frozen=True)
class EvidencePromotionContext:
    requirement_id: str
    requirement_text: str
    semantic_group: SemanticGroup | None
    facets: tuple[RequirementFacet, ...]
    evidence_kind: EvidenceKind | None
    matched_terms: tuple[str, ...]
    kpi_row_label: str | None
    kpi_row_unit: str | None
    kpi_row_value: str | None
    source_text: str
    profile_candidate_unmatched: bool = False


@dataclass(frozen=True)
class EvidencePromotionDecision:
    promote: bool
    max_verdict: AssessmentVerdict
    reason: str


def evaluate_evidence_promotion(context: EvidencePromotionContext) -> EvidencePromotionDecision:
    requirement = " ".join(context.requirement_text.lower().split())
    source = " ".join(context.source_text.lower().split())

    if (
        context.profile_candidate_unmatched
        and not context.matched_terms
        and not context.kpi_row_label
        and not _has_semantic_management_anchor(context.semantic_group, source)
    ):
        return _reject("Profile candidate has no leaf-level anchor or KPI row match.")

    if context.semantic_group is SemanticGroup.GHG_EMISSIONS_KPI and _is_reduction_requirement(requirement):
        if _contains_any(source, ("预计", "预估", "预测", "expected", "estimated", "projected")):
            return EvidencePromotionDecision(
                promote=True,
                max_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                reason="Estimated or projected reduction evidence cannot establish actual reporting-period reductions.",
            )

    if context.semantic_group is SemanticGroup.ENERGY_KPI and _contains_any(
        requirement,
        ("total energy consumption", "total energy use", "总能耗", "能源使用总量"),
    ):
        if _contains_any(source, ("主要能源", "selected energy", "major energy")) and not _contains_any(
            source,
            ("能源使用总量", "总能耗", "total energy consumption", "total energy use"),
        ):
            return EvidencePromotionDecision(
                promote=True,
                max_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                reason="Selected or major energy components do not establish total energy consumption.",
            )

    if context.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT:
        supplier_count_shape = (
            _contains_any(source, ("供应商数量", "商数量", "supplier count", "number of suppliers"))
            and _contains_any(source, ("供应", "supplier"))
        )
        negative_impact_shape = _contains_any(
            source,
            ("负面环境影响", "负面社会影响", "negative environmental impact", "negative social impact"),
        )
        if RequirementFacet.REQUIRES_COUNT in context.facets and supplier_count_shape and negative_impact_shape:
            return EvidencePromotionDecision(
                promote=True,
                max_verdict=AssessmentVerdict.DISCLOSED,
                reason="The bounded KPI row discloses the supplier count for the required negative-impact scope.",
            )
        if (
            RequirementFacet.REQUIRES_PERCENTAGE in context.facets
            and _contains_any(source, ("一致同意改进", "improvements were agreed", "agreed improvements"))
            and _contains_any(source, ("供应商百分比", "supplier percentage", "%"))
        ):
            return EvidencePromotionDecision(
                promote=True,
                max_verdict=AssessmentVerdict.DISCLOSED,
                reason="The bounded KPI row discloses the agreed-improvement supplier percentage.",
            )
        if _has_direct_leaf_kpi_anchor(context) and any(
            term.lower() in source for term in context.matched_terms
        ):
            return EvidencePromotionDecision(
                promote=True,
                max_verdict=AssessmentVerdict.DISCLOSED,
                reason="A leaf-specific supplier KPI label matched the bounded source text.",
            )
        if RequirementFacet.REQUIRES_COUNT in context.facets:
            has_supplier_count = bool(
                re.search(r"(?:供应商[^。；\n]{0,24})?\d[\d,]*(?:\.\d+)?\s*(?:家|个)", source)
                or re.search(r"\b\d[\d,]*(?:\.\d+)?\s+suppliers?\b", source)
            )
            has_percentage_only = "%" in source or "百分比" in source or "覆盖率" in source
            if has_percentage_only and not has_supplier_count:
                return EvidencePromotionDecision(
                    promote=True,
                    max_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                    reason="Supplier percentage evidence does not establish the supplier count required by the leaf.",
                )
        if _contains_any(requirement, ("negative social impact", "negative environmental impact", "负面社会影响", "负面环境影响")):
            if not _contains_any(source, ("负面影响", "重大影响", "negative impact", "adverse impact")):
                if _contains_any(source, ("社会责任审核", "社会评价", "social audit", "social responsibility")):
                    return EvidencePromotionDecision(
                        promote=True,
                        max_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                        reason="Supplier social assessment evidence is relevant but does not identify significant negative impacts.",
                    )
                return _reject("Supplier audit or rating evidence does not identify suppliers with negative impacts.")

    if context.semantic_group is SemanticGroup.OHS_KPI:
        if _contains_any(requirement, ("hours worked", "工作小时", "工作工时")):
            if not _contains_any(source, ("工作小时", "工作工时", "hours worked")) or _contains_any(
                source,
                ("培训时数", "培训小时", "training hours"),
            ):
                return _reject("Training hours do not satisfy hours-worked requirements.")
        if _contains_any(requirement, ("fatalities as a result of work-related ill health", "工作相关健康问题导致的死亡")):
            has_direct_death = _contains_any(
                source,
                ("职业病死亡", "工作相关健康问题死亡", "ill-health fatalities", "fatalities from occupational disease"),
            )
            if not has_direct_death and _contains_any(source, ("职业病", "工作相关健康", "ill health", "occupational disease")):
                return EvidencePromotionDecision(
                    promote=True,
                    max_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                    reason="Occupational disease cases are relevant but do not directly disclose ill-health fatalities.",
                )
            if not has_direct_death:
                return _reject("Evidence does not establish work-related ill-health fatalities.")

    if context.semantic_group is SemanticGroup.NOTICE_PERIOD and _contains_any(
        requirement,
        ("minimum number of weeks", "最短通知周数"),
    ):
        if not _contains_any(source, ("周", "星期", "week")):
            return _reject("General employee communication does not establish a minimum notice period in weeks.")

    if context.semantic_group is SemanticGroup.EMPLOYEE_KPI and _contains_any(
        requirement,
        ("returned to work after parental leave", "育儿假结束后返岗", "育儿假结束后返回"),
    ):
        has_leave_return = _contains_any(source, ("育儿假", "产假", "parental leave")) and _contains_any(
            source,
            ("返岗", "返回工作", "returned to work"),
        )
        has_gender = _contains_any(source, ("男性", "女性", "按性别", "by gender", "male", "female"))
        if not (has_leave_return and has_gender):
            return _reject("General workforce data does not establish parental-leave returns by gender.")

    if _has_direct_leaf_kpi_anchor(context):
        return EvidencePromotionDecision(
            promote=True,
            max_verdict=AssessmentVerdict.DISCLOSED,
            reason="A leaf-specific KPI label matched within the bounded profile route.",
        )

    return EvidencePromotionDecision(
        promote=True,
        max_verdict=AssessmentVerdict.DISCLOSED,
        reason="Evidence passes the applicable leaf-level promotion checks.",
    )


def _reject(reason: str) -> EvidencePromotionDecision:
    return EvidencePromotionDecision(
        promote=False,
        max_verdict=AssessmentVerdict.UNKNOWN,
        reason=reason,
    )


def _is_reduction_requirement(requirement: str) -> bool:
    return _contains_any(requirement, ("emissions reduced", "emission reductions", "减排量", "排放减少"))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _has_direct_leaf_kpi_anchor(context: EvidencePromotionContext) -> bool:
    if context.evidence_kind is not EvidenceKind.KPI_VALUE:
        return False
    direct_markers = (
        "数量",
        "百分比",
        "比率",
        "死亡",
        "总量",
        "排放量",
        "一致同意改进",
        "number",
        "percentage",
        "rate",
        "fatalit",
        "total",
    )
    candidates = [*context.matched_terms]
    if context.kpi_row_label:
        candidates.append(context.kpi_row_label)
    return any(_contains_any(term.lower(), direct_markers) for term in candidates)


def _has_semantic_management_anchor(semantic_group: SemanticGroup | None, source: str) -> bool:
    if semantic_group is SemanticGroup.ANTI_CORRUPTION_RISK:
        return _contains_any(source, ("反腐败", "反舞弊", "腐败", "商业道德", "审计策略", "corruption", "anti-fraud"))
    if semantic_group is SemanticGroup.OHS_MANAGEMENT:
        return _contains_any(source, ("职业健康", "安全管理", "iso 45001", "ehs", "occupational health", "safety management"))
    if semantic_group is SemanticGroup.OHS_KPI:
        return _contains_any(source, ("职业病", "因工死亡", "工伤", "重大安全事故", "work-related injury", "ill health"))
    if semantic_group is SemanticGroup.WASTE_KPI:
        return _contains_any(source, ("废弃物", "危废", "固体废物", "waste"))
    if semantic_group is SemanticGroup.TRAINING_PROGRAM:
        return _contains_any(source, ("培训", "技能提升", "员工发展", "training", "skill"))
    if semantic_group is SemanticGroup.HUMAN_RIGHTS_POLICY:
        return _contains_any(source, ("人权", "童工", "强迫劳动", "结社", "集体谈判", "员工权益", "human rights", "child labor"))
    if semantic_group is SemanticGroup.COMMUNITY_PROGRAM:
        return _contains_any(source, ("社区", "公益", "影响评估", "发展项目", "community", "impact assessment"))
    if semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT:
        return _contains_any(source, ("社会责任", "社会评价", "劳工", "人权", "商业道德", "social responsibility", "social criteria"))
    return False
