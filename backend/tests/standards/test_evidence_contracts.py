from src.domain.enums import AssessmentVerdict, ReviewStatus
from src.standards.evidence_contracts import get_requirement_contract
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup


def test_evidence_contract_returns_305_2_allowed_and_forbidden_pages():
    contract = get_requirement_contract("GRI 305-2-a")

    assert contract is not None
    assert contract.requirement_id == "GRI 305-2-a"
    assert contract.allowed_pages == (20, 63)
    assert contract.forbidden_pages == (3,)
    assert contract.candidate_pages == (20, 63)
    assert contract.kpi_table_pages == (63,)
    assert contract.verdict is AssessmentVerdict.DISCLOSED
    assert contract.review_status is ReviewStatus.NOT_REQUIRED


def test_evidence_contract_returns_unknown_only_305_2_c():
    contract = get_requirement_contract("GRI 305-2-c")

    assert contract is not None
    assert contract.requirement_id == "GRI 305-2-c"
    assert contract.allowed_pages == ()
    assert contract.candidate_pages == ()
    assert contract.verdict is AssessmentVerdict.UNKNOWN
    assert contract.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW


def test_supplier_environmental_and_social_contracts_share_semantic_group():
    contract_308 = get_requirement_contract("GRI 308-1-a")
    contract_414 = get_requirement_contract("GRI 414-1-a")

    assert contract_308 is not None
    assert contract_414 is not None
    assert contract_308.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
    assert contract_414.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
    assert RequirementFacet.REQUIRES_PERCENTAGE in contract_308.facets
    assert RequirementFacet.REQUIRES_PERCENTAGE in contract_414.facets


def test_supplier_assessment_contracts_have_shared_ontology_metadata():
    cases = {
        "GRI 308-1-a": {RequirementFacet.REQUIRES_PERCENTAGE},
        "GRI 308-2-a": {RequirementFacet.REQUIRES_COUNT},
        "GRI 308-2-b": {RequirementFacet.REQUIRES_COUNT},
        "GRI 308-2-c": {RequirementFacet.REQUIRES_IMPACT_TYPE},
        "GRI 308-2-d": {RequirementFacet.REQUIRES_PERCENTAGE},
        "GRI 308-2-e": {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
        "GRI 414-1-a": {RequirementFacet.REQUIRES_PERCENTAGE},
        "GRI 414-2-a": {RequirementFacet.REQUIRES_COUNT},
        "GRI 414-2-b": {RequirementFacet.REQUIRES_COUNT},
        "GRI 414-2-c": {RequirementFacet.REQUIRES_IMPACT_TYPE},
        "GRI 414-2-d": {RequirementFacet.REQUIRES_COUNT},
        "GRI 414-2-e": {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
    }

    for requirement_id, expected_facets in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
        assert set(contract.facets) == expected_facets
        assert EvidenceKind.KPI_VALUE in contract.evidence_kinds


def test_ohs_injury_and_ill_health_contracts_share_semantic_group():
    contract_403_9 = get_requirement_contract("GRI 403-9-a-iii")
    contract_403_10 = get_requirement_contract("GRI 403-10-a-ii")

    assert contract_403_9 is not None
    assert contract_403_10 is not None
    assert contract_403_9.semantic_group is SemanticGroup.OHS_KPI
    assert contract_403_10.semantic_group is SemanticGroup.OHS_KPI
    assert RequirementFacet.REQUIRES_COUNT in contract_403_9.facets
    assert RequirementFacet.REQUIRES_COUNT in contract_403_10.facets


def test_training_and_diversity_contracts_share_breakdown_dimension_group():
    contract_404 = get_requirement_contract("GRI 404-1-a")
    contract_405 = get_requirement_contract("GRI 405-1-b")

    assert contract_404 is not None
    assert contract_405 is not None
    assert contract_404.semantic_group is SemanticGroup.BREAKDOWN_DIMENSION
    assert contract_405.semantic_group is SemanticGroup.BREAKDOWN_DIMENSION
    assert RequirementFacet.REQUIRES_GENDER_BREAKDOWN in contract_404.facets
    assert RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN in contract_405.facets
