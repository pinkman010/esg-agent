from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Iterable

from src.domain.enums import AssessmentVerdict, ReviewStatus


class RequirementFacet(StrEnum):
    REQUIRES_COUNT = "requires_count"
    REQUIRES_PERCENTAGE = "requires_percentage"
    REQUIRES_GENDER_BREAKDOWN = "requires_gender_breakdown"
    REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN = "requires_employee_category_breakdown"
    REQUIRES_REGION_BREAKDOWN = "requires_region_breakdown"
    REQUIRES_METHOD_OR_ASSUMPTION = "requires_method_or_assumption"
    REQUIRES_WORKER_BOUNDARY = "requires_worker_boundary"
    REQUIRES_RISK_LOCATION = "requires_risk_location"
    REQUIRES_IMPACT_TYPE = "requires_impact_type"
    REQUIRES_REMEDIATION_STATUS = "requires_remediation_status"
    REQUIRES_REASON_WHY = "requires_reason_why"
    REQUIRES_GOVERNANCE_BODY = "requires_governance_body"
    REQUIRES_SECURITY_PERSONNEL = "requires_security_personnel"
    REQUIRES_INCIDENT_CLASSIFICATION = "requires_incident_classification"
    REQUIRES_COMPLAINT_SOURCE_BREAKDOWN = "requires_complaint_source_breakdown"


class EvidenceKind(StrEnum):
    KPI_VALUE = "kpi_value"
    KPI_BREAKDOWN = "kpi_breakdown"
    EXPLICIT_ZERO_STATEMENT = "explicit_zero_statement"
    POLICY = "policy"
    MANAGEMENT_MECHANISM = "management_mechanism"
    CASE = "case"
    RISK_IDENTIFICATION_RESULT = "risk_identification_result"
    METHODOLOGY = "methodology"
    INDEX_STATEMENT = "index_statement"
    OMISSION_NOTE = "omission_note"


class SemanticGroup(StrEnum):
    SUPPLIER_ASSESSMENT = "supplier_assessment"
    OHS_KPI = "ohs_kpi"
    BREAKDOWN_DIMENSION = "breakdown_dimension"
    HUMAN_RIGHTS_TRAINING = "human_rights_training"
    ZERO_EVENT_COMPLIANCE = "zero_event_compliance"
    GHG_EMISSIONS_KPI = "ghg_emissions_kpi"
    ENERGY_KPI = "energy_kpi"
    WATER_KPI = "water_kpi"
    WASTE_KPI = "waste_kpi"


@dataclass(frozen=True)
class OntologyVerdictResult:
    verdict: AssessmentVerdict
    review_status: ReviewStatus
    rationale: str
    missing_items: tuple[str, ...] = ()


def evaluate_ontology_verdict(
    *,
    semantic_group: SemanticGroup | None,
    facets: Iterable[RequirementFacet],
    evidence_kinds: Iterable[EvidenceKind],
) -> OntologyVerdictResult:
    facets = set(facets)
    evidence_kinds = set(evidence_kinds)
    if EvidenceKind.OMISSION_NOTE in evidence_kinds:
        return OntologyVerdictResult(
            verdict=AssessmentVerdict.UNKNOWN,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
            rationale="Omission notes explain gaps but do not constitute substantive disclosure evidence.",
            missing_items=("substantive disclosure evidence",),
        )

    if semantic_group is SemanticGroup.HUMAN_RIGHTS_TRAINING and RequirementFacet.REQUIRES_SECURITY_PERSONNEL in facets:
        return OntologyVerdictResult(
            verdict=AssessmentVerdict.UNKNOWN,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
            rationale="General training or management mechanism evidence does not satisfy security personnel human rights training disclosure.",
            missing_items=("security personnel human rights training percentage",),
        )

    if semantic_group is SemanticGroup.ZERO_EVENT_COMPLIANCE:
        if RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION in facets:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Explicit zero-event evidence is directionally relevant, but it does not classify non-compliance incidents by regulatory or voluntary-code category.",
                missing_items=("不合规事件分类",),
            )
        if RequirementFacet.REQUIRES_COMPLAINT_SOURCE_BREAKDOWN in facets:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.UNKNOWN,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="A general zero complaint statement does not split complaints by source.",
                missing_items=("投诉来源分类",),
            )
        if EvidenceKind.EXPLICIT_ZERO_STATEMENT in evidence_kinds and RequirementFacet.REQUIRES_COUNT in facets:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.DISCLOSED,
                review_status=ReviewStatus.NOT_REQUIRED,
                rationale="Explicit zero-event evidence directly satisfies the count or concise no-incident statement requirement.",
            )

    if semantic_group is SemanticGroup.GHG_EMISSIONS_KPI:
        if RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in facets and EvidenceKind.METHODOLOGY in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="GHG methodology evidence is directionally relevant, but the full GRI-required method, factor, GWP, gas, base-year, or boundary detail remains subject to sufficiency review.",
                missing_items=("完整温室气体核算方法或排放因子口径",),
            )
        if RequirementFacet.REQUIRES_COUNT in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.DISCLOSED,
                review_status=ReviewStatus.NOT_REQUIRED,
                rationale="GHG KPI evidence directly satisfies the emissions amount requirement.",
            )

    if semantic_group is SemanticGroup.ENERGY_KPI:
        if RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Energy KPI evidence is directionally relevant, but the full GRI-required energy type, unit, baseline, method, assumption, or calculation-tool detail remains subject to sufficiency review.",
                missing_items=("完整能源类型、单位或方法口径",),
            )
        if RequirementFacet.REQUIRES_COUNT in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.DISCLOSED,
                review_status=ReviewStatus.NOT_REQUIRED,
                rationale="Energy KPI evidence directly satisfies the energy amount requirement.",
            )

    if semantic_group is SemanticGroup.WATER_KPI:
        if RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in facets and (
            EvidenceKind.KPI_VALUE in evidence_kinds or EvidenceKind.MANAGEMENT_MECHANISM in evidence_kinds
        ):
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Water evidence is directionally relevant, but the full GRI-required water source, discharge destination, stress-area, standard, method, or compilation detail remains subject to sufficiency review.",
                missing_items=("完整水源、排放目的地、高水风险区域或方法口径",),
            )

    if semantic_group is SemanticGroup.WASTE_KPI:
        if RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in facets and (
            EvidenceKind.KPI_VALUE in evidence_kinds or EvidenceKind.MANAGEMENT_MECHANISM in evidence_kinds
        ):
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Waste evidence is directionally relevant, but the full GRI-required waste composition, impact boundary, recovery operation, disposal route, third-party process, or compilation detail remains subject to sufficiency review.",
                missing_items=("完整废弃物组成、回收操作、处置去向或方法口径",),
            )

    if semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT:
        if RequirementFacet.REQUIRES_REASON_WHY in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="KPI evidence is directionally relevant, but the reason why supplier relationships were terminated is missing.",
                missing_items=("终止关系原因说明",),
            )
        if RequirementFacet.REQUIRES_REASON_WHY in facets and EvidenceKind.MANAGEMENT_MECHANISM in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Supplier exit mechanism evidence is directionally relevant, but it does not disclose the termination percentage or reasons.",
                missing_items=("终止关系百分比", "终止关系原因说明"),
            )
        if RequirementFacet.REQUIRES_IMPACT_TYPE in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="KPI evidence discloses supplier impact assessment results, but it does not describe the significant impact types.",
                missing_items=("重大负面影响类型",),
            )

    if semantic_group is SemanticGroup.OHS_KPI:
        if RequirementFacet.REQUIRES_WORKER_BOUNDARY in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="OHS KPI evidence is directionally relevant, but the worker boundary is narrower than the GRI-controlled worker scope.",
                missing_items=("受组织控制的非雇员工作者口径",),
            )
        if RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in facets and EvidenceKind.METHODOLOGY in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.DISCLOSED,
                review_status=ReviewStatus.NOT_REQUIRED,
                rationale="Methodology evidence directly satisfies the OHS rate basis or method requirement.",
            )
        if RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="OHS KPI evidence is directionally relevant, but the full scope, method, or assumptions are missing.",
                missing_items=("完整口径或方法说明",),
            )
        if RequirementFacet.REQUIRES_IMPACT_TYPE in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="OHS KPI evidence is directionally relevant, but it does not disclose the required injury or ill-health types and hazards.",
                missing_items=("主要类型或危害清单",),
            )

    if (
        semantic_group is SemanticGroup.BREAKDOWN_DIMENSION
        and RequirementFacet.REQUIRES_GOVERNANCE_BODY in facets
        and EvidenceKind.KPI_VALUE in evidence_kinds
    ):
        return OntologyVerdictResult(
            verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
            rationale="Management-level KPI evidence is directionally relevant, but it does not confirm the governance body scope.",
            missing_items=("治理机构口径确认",),
        )

    if _requires_breakdown(facets) and EvidenceKind.KPI_BREAKDOWN not in evidence_kinds:
        return OntologyVerdictResult(
            verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
            rationale="Overall KPI evidence is directionally relevant, but required breakdown dimensions are missing.",
            missing_items=_breakdown_missing_items(facets),
        )

    if RequirementFacet.REQUIRES_PERCENTAGE in facets:
        if EvidenceKind.KPI_VALUE in evidence_kinds or EvidenceKind.KPI_BREAKDOWN in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.DISCLOSED,
                review_status=ReviewStatus.NOT_REQUIRED,
                rationale="KPI evidence directly satisfies the percentage requirement.",
            )
        if EvidenceKind.MANAGEMENT_MECHANISM in evidence_kinds or EvidenceKind.POLICY in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Management evidence is directionally relevant, but the required percentage is missing.",
                missing_items=("percentage",),
            )

    if RequirementFacet.REQUIRES_COUNT in facets:
        if EvidenceKind.KPI_VALUE in evidence_kinds or EvidenceKind.EXPLICIT_ZERO_STATEMENT in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.DISCLOSED,
                review_status=ReviewStatus.NOT_REQUIRED,
                rationale="Evidence directly satisfies the count requirement.",
            )

    return OntologyVerdictResult(
        verdict=AssessmentVerdict.UNKNOWN,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        rationale="Ontology matrix does not have sufficient evidence to determine disclosure.",
        missing_items=("sufficient evidence",),
    )


def _requires_breakdown(facets: set[RequirementFacet]) -> bool:
    return bool(
        facets
        & {
            RequirementFacet.REQUIRES_GENDER_BREAKDOWN,
            RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN,
            RequirementFacet.REQUIRES_REGION_BREAKDOWN,
        }
    )


def _breakdown_missing_items(facets: set[RequirementFacet]) -> tuple[str, ...]:
    missing: list[str] = []
    if RequirementFacet.REQUIRES_GENDER_BREAKDOWN in facets:
        missing.append("按性别拆分")
    if RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN in facets:
        missing.append("按员工类别拆分")
    if RequirementFacet.REQUIRES_REGION_BREAKDOWN in facets:
        missing.append("按地区拆分")
    return tuple(missing)
