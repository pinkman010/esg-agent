from src.domain.enums import AssessmentVerdict, ReviewStatus
from src.standards.evidence_ontology import (
    EvidenceKind,
    RequirementFacet,
    SemanticGroup,
    evaluate_ontology_verdict,
)


def test_ontology_discloses_percentage_when_kpi_value_matches_percentage_requirement():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.DISCLOSED
    assert result.review_status is ReviewStatus.NOT_REQUIRED
    assert result.missing_items == ()


def test_ontology_marks_breakdown_requirement_partial_when_only_overall_kpi_exists():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.BREAKDOWN_DIMENSION,
        facets={RequirementFacet.REQUIRES_GENDER_BREAKDOWN, RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "按性别拆分" in result.missing_items
    assert "按员工类别拆分" in result.missing_items


def test_ontology_marks_governance_body_breakdown_partial_when_management_kpi_exists():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.BREAKDOWN_DIMENSION,
        facets={RequirementFacet.REQUIRES_GOVERNANCE_BODY},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "治理机构口径确认" in result.missing_items


def test_zero_event_compliance_discloses_direct_zero_count_statement():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.ZERO_EVENT_COMPLIANCE,
        facets={RequirementFacet.REQUIRES_COUNT},
        evidence_kinds={EvidenceKind.EXPLICIT_ZERO_STATEMENT},
    )

    assert result.verdict is AssessmentVerdict.DISCLOSED
    assert result.review_status is ReviewStatus.NOT_REQUIRED


def test_zero_event_compliance_keeps_classification_partial():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.ZERO_EVENT_COMPLIANCE,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION},
        evidence_kinds={EvidenceKind.EXPLICIT_ZERO_STATEMENT},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "不合规事件分类" in result.missing_items


def test_zero_event_compliance_does_not_split_complaint_sources():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.ZERO_EVENT_COMPLIANCE,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_COMPLAINT_SOURCE_BREAKDOWN},
        evidence_kinds={EvidenceKind.EXPLICIT_ZERO_STATEMENT},
    )

    assert result.verdict is AssessmentVerdict.UNKNOWN
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "投诉来源分类" in result.missing_items


def test_ghg_emissions_kpi_discloses_direct_emissions_amount():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.GHG_EMISSIONS_KPI,
        facets={RequirementFacet.REQUIRES_COUNT},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.DISCLOSED
    assert result.review_status is ReviewStatus.NOT_REQUIRED


def test_ghg_emissions_kpi_keeps_methodology_partial():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.GHG_EMISSIONS_KPI,
        facets={RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        evidence_kinds={EvidenceKind.METHODOLOGY},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "完整温室气体核算方法或排放因子口径" in result.missing_items


def test_energy_kpi_discloses_direct_energy_amount():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.ENERGY_KPI,
        facets={RequirementFacet.REQUIRES_COUNT},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.DISCLOSED
    assert result.review_status is ReviewStatus.NOT_REQUIRED


def test_energy_kpi_keeps_method_dependent_items_partial():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.ENERGY_KPI,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "完整能源类型、单位或方法口径" in result.missing_items


def test_water_kpi_keeps_water_source_and_method_items_partial():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.WATER_KPI,
        facets={RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "完整水源、排放目的地、高水风险区域或方法口径" in result.missing_items


def test_waste_kpi_keeps_recovery_and_method_items_partial():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.WASTE_KPI,
        facets={RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "完整废弃物组成、回收操作、处置去向或方法口径" in result.missing_items


def test_ontology_keeps_security_training_unknown_for_general_training_evidence():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.HUMAN_RIGHTS_TRAINING,
        facets={RequirementFacet.REQUIRES_SECURITY_PERSONNEL},
        evidence_kinds={EvidenceKind.MANAGEMENT_MECHANISM},
    )

    assert result.verdict is AssessmentVerdict.UNKNOWN
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "security personnel human rights training percentage" in result.missing_items


def test_supplier_assessment_discloses_direct_kpi_count_or_percentage():
    percentage = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )
    count = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_COUNT},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert percentage.verdict is AssessmentVerdict.DISCLOSED
    assert percentage.review_status is ReviewStatus.NOT_REQUIRED
    assert count.verdict is AssessmentVerdict.DISCLOSED
    assert count.review_status is ReviewStatus.NOT_REQUIRED


def test_supplier_assessment_keeps_impact_type_partial_when_only_kpi_value_exists():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_IMPACT_TYPE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "重大负面影响类型" in result.missing_items


def test_supplier_assessment_keeps_termination_reason_partial_when_reason_is_missing():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "终止关系原因说明" in result.missing_items


def test_supplier_assessment_policy_only_cannot_disclose_quantity_or_percentage():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.MANAGEMENT_MECHANISM},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "percentage" in result.missing_items


def test_supplier_assessment_impact_count_does_not_satisfy_impact_type():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_IMPACT_TYPE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert "重大负面影响类型" in result.missing_items


def test_supplier_assessment_exit_mechanism_does_not_satisfy_percentage_and_reason():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
        evidence_kinds={EvidenceKind.MANAGEMENT_MECHANISM},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "终止关系百分比" in result.missing_items
    assert "终止关系原因说明" in result.missing_items


def test_ohs_kpi_discloses_direct_employee_count_or_hours():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.OHS_KPI,
        facets={RequirementFacet.REQUIRES_COUNT},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.DISCLOSED
    assert result.review_status is ReviewStatus.NOT_REQUIRED


def test_ohs_kpi_discloses_rate_basis_when_methodology_evidence_matches():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.OHS_KPI,
        facets={RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        evidence_kinds={EvidenceKind.METHODOLOGY},
    )

    assert result.verdict is AssessmentVerdict.DISCLOSED
    assert result.review_status is ReviewStatus.NOT_REQUIRED


def test_ohs_kpi_keeps_external_worker_boundary_partial():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.OHS_KPI,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "受组织控制的非雇员工作者口径" in result.missing_items


def test_ohs_kpi_keeps_incomplete_ill_health_scope_partial():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.OHS_KPI,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "完整口径或方法说明" in result.missing_items


def test_ohs_kpi_hazard_type_is_not_satisfied_by_kpi_value():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.OHS_KPI,
        facets={RequirementFacet.REQUIRES_IMPACT_TYPE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "主要类型或危害清单" in result.missing_items
