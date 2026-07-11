import pytest

from src.domain.enums import AssessmentVerdict
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup
from src.tools.evidence_promotion import EvidencePromotionContext, evaluate_evidence_promotion


def _context(
    requirement_text: str,
    source_text: str,
    *,
    semantic_group: SemanticGroup | None = None,
    facets: tuple[RequirementFacet, ...] = (),
    evidence_kind: EvidenceKind | None = None,
    profile_candidate_unmatched: bool = False,
    matched_terms: tuple[str, ...] = (),
) -> EvidencePromotionContext:
    return EvidencePromotionContext(
        requirement_id="GRI test",
        requirement_text=requirement_text,
        semantic_group=semantic_group,
        facets=facets,
        evidence_kind=evidence_kind,
        matched_terms=matched_terms,
        kpi_row_label=None,
        kpi_row_unit=None,
        kpi_row_value=None,
        source_text=source_text,
        profile_candidate_unmatched=profile_candidate_unmatched,
    )


def test_estimated_ghg_reduction_is_capped_at_partial() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "GHG emissions reduced as a direct result of reduction initiatives",
            "项目预估年度碳减排量为 158 tCO2e",
            semantic_group=SemanticGroup.GHG_EMISSIONS_KPI,
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.PARTIALLY_DISCLOSED


@pytest.mark.parametrize(
    ("requirement_text", "source_text", "semantic_group"),
    [
        (
            "number of suppliers identified as having significant actual and potential negative social impacts",
            "绿色供应商审核覆盖率 100%",
            SemanticGroup.SUPPLIER_ASSESSMENT,
        ),
        (
            "number of hours worked for employees",
            "员工安全培训时数 441630 小时",
            SemanticGroup.OHS_KPI,
        ),
        (
            "minimum number of weeks notice typically provided prior to significant operational changes",
            "公司建立员工沟通和申诉机制",
            SemanticGroup.NOTICE_PERIOD,
        ),
        (
            "employees that returned to work after parental leave by gender",
            "员工总数及女性员工占比",
            SemanticGroup.EMPLOYEE_KPI,
        ),
    ],
)
def test_wrong_leaf_evidence_is_not_promoted(
    requirement_text: str,
    source_text: str,
    semantic_group: SemanticGroup,
) -> None:
    decision = evaluate_evidence_promotion(
        _context(
            requirement_text,
            source_text,
            semantic_group=semantic_group,
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.promote is False
    assert decision.max_verdict is AssessmentVerdict.UNKNOWN


def test_unmatched_profile_candidate_remains_candidate_only() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "percentage of new suppliers screened using social criteria",
            "绿色供应链和供应商绿电比例",
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            facets=(RequirementFacet.REQUIRES_NEW_SUPPLIER_SCOPE,),
            evidence_kind=EvidenceKind.KPI_VALUE,
            profile_candidate_unmatched=True,
        )
    )

    assert decision.promote is False


def test_matching_ohs_hours_row_is_promoted() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "number of hours worked for employees",
            "员工工作小时数 44528901 小时",
            semantic_group=SemanticGroup.OHS_KPI,
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.DISCLOSED


def test_social_supplier_audit_is_partial_for_negative_impact_count() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "number of suppliers identified as having significant actual and potential negative social impacts",
            "完成 85 家供应商社会责任审核，A级 83 家，B级 2 家",
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            evidence_kind=EvidenceKind.KPI_VALUE,
            profile_candidate_unmatched=True,
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.PARTIALLY_DISCLOSED


def test_occupational_disease_cases_are_partial_for_ill_health_fatalities() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "number of fatalities as a result of work-related  ill health",
            "职业病发病次数为 0",
            semantic_group=SemanticGroup.OHS_KPI,
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.PARTIALLY_DISCLOSED


def test_supplier_assessment_percentage_is_partial_for_assessed_supplier_count() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "number of suppliers assessed for environmental impacts",
            "绿色供应商审核覆盖率 100%",
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            facets=(RequirementFacet.REQUIRES_COUNT,),
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.PARTIALLY_DISCLOSED


def test_mixed_ohs_page_does_not_turn_disease_cases_into_ill_health_fatalities() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "number of fatalities as a result of work-related ill health",
            "员工因工死亡人数 1；职业病发病次数 0",
            semantic_group=SemanticGroup.OHS_KPI,
            facets=(RequirementFacet.REQUIRES_COUNT,),
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.PARTIALLY_DISCLOSED


def test_major_energy_components_are_partial_for_total_energy_consumption() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "total energy consumption within the organization",
            "主要能源和资源使用量及密度：用电量、天然气使用量",
            semantic_group=SemanticGroup.ENERGY_KPI,
            facets=(RequirementFacet.REQUIRES_COUNT,),
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.PARTIALLY_DISCLOSED


def test_direct_leaf_kpi_anchor_wins_over_neighbor_table_rows() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "number of suppliers assessed for environmental impacts",
            "开展环境影响评估的供应商数量（个）85；绿色供应商审核覆盖率100%",
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            facets=(RequirementFacet.REQUIRES_COUNT,),
            evidence_kind=EvidenceKind.KPI_VALUE,
            matched_terms=("开展环境影响评估的供应商数量",),
        )
    )

    assert decision.promote is True
    assert decision.max_verdict is AssessmentVerdict.DISCLOSED


def test_interleaved_supplier_kpi_still_satisfies_negative_impact_count() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "number of suppliers identified as having significant actual and potential negative social impacts",
            "具有重大实际/潜在负面社会影响的供应 0 / / 商数量（个）",
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            facets=(RequirementFacet.REQUIRES_COUNT,),
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.max_verdict is AssessmentVerdict.DISCLOSED


def test_interleaved_supplier_kpi_still_satisfies_agreed_improvement_percentage() -> None:
    decision = evaluate_evidence_promotion(
        _context(
            "percentage of suppliers with negative environmental impacts with which improvements were agreed",
            "具有重大实际/潜在负面环境影响，且评 0 0 0 工作小时数 估后一致同意改进的供应商百分比（%）",
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            facets=(RequirementFacet.REQUIRES_PERCENTAGE,),
            evidence_kind=EvidenceKind.KPI_VALUE,
        )
    )

    assert decision.max_verdict is AssessmentVerdict.DISCLOSED
