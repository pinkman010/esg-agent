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


def test_ontology_keeps_security_training_unknown_for_general_training_evidence():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.HUMAN_RIGHTS_TRAINING,
        facets={RequirementFacet.REQUIRES_SECURITY_PERSONNEL},
        evidence_kinds={EvidenceKind.MANAGEMENT_MECHANISM},
    )

    assert result.verdict is AssessmentVerdict.UNKNOWN
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "security personnel human rights training percentage" in result.missing_items
