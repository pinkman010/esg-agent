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
    assert contract.verdict is None
    assert contract.review_status is None
    assert contract.semantic_group is SemanticGroup.GHG_EMISSIONS_KPI
    assert contract.facets == (RequirementFacet.REQUIRES_COUNT,)
    assert contract.evidence_kinds == (EvidenceKind.KPI_VALUE,)


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


def test_ohs_kpi_contracts_have_pilot_ontology_metadata():
    cases = {
        "GRI 403-9-a-i": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-a-ii": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_IMPACT_TYPE}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-a-iii": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-a-v": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-b-i": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-b-iii": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-b-v": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-e": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.METHODOLOGY}),
        "GRI 403-10-a-i": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-a-ii": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-b-i": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-b-ii": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.KPI_VALUE},
        ),
    }

    for requirement_id, (expected_facets, expected_evidence_kinds) in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.OHS_KPI
        assert set(contract.facets) == expected_facets
        assert set(contract.evidence_kinds) == expected_evidence_kinds


def test_training_and_diversity_contracts_share_breakdown_dimension_group():
    contract_404 = get_requirement_contract("GRI 404-1-a")
    contract_405 = get_requirement_contract("GRI 405-1-b")

    assert contract_404 is not None
    assert contract_405 is not None
    assert contract_404.semantic_group is SemanticGroup.BREAKDOWN_DIMENSION
    assert contract_405.semantic_group is SemanticGroup.BREAKDOWN_DIMENSION
    assert RequirementFacet.REQUIRES_GENDER_BREAKDOWN in contract_404.facets
    assert RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN in contract_405.facets


def test_breakdown_dimension_contracts_have_pilot_ontology_metadata():
    cases = {
        "GRI 404-1-a": {RequirementFacet.REQUIRES_GENDER_BREAKDOWN, RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 404-3-a": {RequirementFacet.REQUIRES_GENDER_BREAKDOWN, RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 405-1-a": {RequirementFacet.REQUIRES_GOVERNANCE_BODY},
        "GRI 405-1-a-i": {RequirementFacet.REQUIRES_GOVERNANCE_BODY, RequirementFacet.REQUIRES_GENDER_BREAKDOWN},
        "GRI 405-1-a-ii": {RequirementFacet.REQUIRES_GOVERNANCE_BODY, RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 405-1-a-iii": {RequirementFacet.REQUIRES_GOVERNANCE_BODY, RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 405-1-b": {RequirementFacet.REQUIRES_GENDER_BREAKDOWN, RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 405-1-b-i": {RequirementFacet.REQUIRES_GENDER_BREAKDOWN, RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 405-1-b-ii": {RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 405-1-b-iii": {RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN},
        "GRI 405-2-a": {RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN, RequirementFacet.REQUIRES_REGION_BREAKDOWN},
    }

    for requirement_id, expected_facets in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.BREAKDOWN_DIMENSION
        assert set(contract.facets) == expected_facets
        assert EvidenceKind.KPI_VALUE in contract.evidence_kinds


def test_zero_event_compliance_contracts_have_pilot_ontology_metadata():
    cases = {
        "GRI 416-2-a": {
            RequirementFacet.REQUIRES_COUNT,
            RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,
        },
        "GRI 416-2-b": {
            RequirementFacet.REQUIRES_COUNT,
            RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,
        },
        "GRI 418-1-a": {RequirementFacet.REQUIRES_COUNT},
        "GRI 418-1-c": {RequirementFacet.REQUIRES_COUNT},
    }

    for requirement_id, expected_facets in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.ZERO_EVENT_COMPLIANCE
        assert set(contract.facets) == expected_facets
        assert EvidenceKind.EXPLICIT_ZERO_STATEMENT in contract.evidence_kinds
        assert contract.verdict is None
        assert contract.review_status is None


def test_ghg_emissions_contracts_have_ontology_metadata():
    cases = {
        "GRI 305-1-a": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 305-1-e": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.METHODOLOGY}),
        "GRI 305-1-g": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.METHODOLOGY}),
        "GRI 305-2-a": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 305-2-b": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 305-2-e": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.METHODOLOGY}),
        "GRI 305-2-g": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.METHODOLOGY}),
        "GRI 305-3-a": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 305-3-f": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.METHODOLOGY}),
        "GRI 305-5-a": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
    }

    for requirement_id, (expected_facets, expected_evidence_kinds) in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.GHG_EMISSIONS_KPI
        assert set(contract.facets) == expected_facets
        assert set(contract.evidence_kinds) == expected_evidence_kinds
        assert contract.verdict is None
        assert contract.review_status is None


def test_energy_contracts_have_ontology_metadata():
    cases = {
        "GRI 302-1-a": {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        "GRI 302-1-c": {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        "GRI 302-1-e": {RequirementFacet.REQUIRES_COUNT},
        "GRI 302-4-a": {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
        "GRI 302-4-b": {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
    }

    for requirement_id, expected_facets in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.ENERGY_KPI
        assert set(contract.facets) == expected_facets
        assert contract.evidence_kinds == (EvidenceKind.KPI_VALUE,)
        assert contract.verdict is None
        assert contract.review_status is None
