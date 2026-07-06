from src.domain.enums import AssessmentVerdict, ReviewStatus
from src.standards.evidence_contracts import get_requirement_contract
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup
from src.standards.no_evidence_guardrails import NoEvidenceGuardrailCategory, get_no_evidence_guardrail


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


def test_evidence_contract_returns_no_evidence_metadata_for_305_2_c():
    contract = get_requirement_contract("GRI 305-2-c")
    guardrail = get_no_evidence_guardrail("GRI 305-2-c")

    assert contract is not None
    assert contract.requirement_id == "GRI 305-2-c"
    assert contract.allowed_pages == ()
    assert contract.candidate_pages == ()
    assert contract.verdict is None
    assert contract.review_status is None
    assert contract.semantic_group is SemanticGroup.GHG_EMISSIONS_KPI
    assert RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in contract.facets
    assert guardrail is not None
    assert guardrail.category is NoEvidenceGuardrailCategory.METHOD_SCOPE
    assert "温室气体种类" in guardrail.missing_items


def test_supplier_environmental_and_social_contracts_share_semantic_group():
    contract_308 = get_requirement_contract("GRI 308-1-a")
    contract_414 = get_requirement_contract("GRI 414-1-a")

    assert contract_308 is not None
    assert contract_414 is not None
    assert contract_308.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
    assert contract_414.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
    assert RequirementFacet.REQUIRES_PERCENTAGE in contract_308.facets
    assert RequirementFacet.REQUIRES_PERCENTAGE in contract_414.facets


def test_kpi_profile_owned_requirement_contract_keeps_semantic_metadata_without_candidate_page():
    contract = get_requirement_contract("GRI 414-1-a")

    assert contract is not None
    assert contract.candidate_pages is None or contract.candidate_pages == ()
    assert contract.kpi_table_pages == (67,)
    assert contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
    assert contract.evidence_kinds == (EvidenceKind.KPI_VALUE,)


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
        "GRI 414-2-d": {RequirementFacet.REQUIRES_PERCENTAGE},
        "GRI 414-2-e": {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
    }

    for requirement_id, expected_facets in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
        assert set(contract.facets) == expected_facets
        expected_kind = EvidenceKind.MANAGEMENT_MECHANISM if requirement_id == "GRI 414-2-d" else EvidenceKind.KPI_VALUE
        assert expected_kind in contract.evidence_kinds


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
        "GRI 403-9-a": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-a-i": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-a-ii": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_IMPACT_TYPE}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-a-iii": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-a-v": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-b": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-b-i": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-b-ii": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY, RequirementFacet.REQUIRES_IMPACT_TYPE},
            {EvidenceKind.KPI_VALUE},
        ),
        "GRI 403-9-b-iii": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-b-v": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-c": ({RequirementFacet.REQUIRES_IMPACT_TYPE}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-d": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-9-e": ({RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.METHODOLOGY}),
        "GRI 403-10-a": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-a-i": ({RequirementFacet.REQUIRES_COUNT}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-a-ii": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-b": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.KPI_VALUE},
        ),
        "GRI 403-10-b-i": ({RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-b-ii": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_WORKER_BOUNDARY, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.KPI_VALUE},
        ),
        "GRI 403-10-c": ({RequirementFacet.REQUIRES_IMPACT_TYPE}, {EvidenceKind.KPI_VALUE}),
        "GRI 403-10-c-i": ({RequirementFacet.REQUIRES_IMPACT_TYPE}, {EvidenceKind.KPI_VALUE}),
    }

    for requirement_id, (expected_facets, expected_evidence_kinds) in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.OHS_KPI
        assert set(contract.facets) == expected_facets
        assert set(contract.evidence_kinds) == expected_evidence_kinds


def test_ohs_management_contracts_have_ontology_metadata():
    management_items = {
        "GRI 403-1-a",
        "GRI 403-1-a-ii",
        "GRI 403-1-b",
        "GRI 403-2-a",
        "GRI 403-2-a-i",
        "GRI 403-2-a-ii",
        "GRI 403-2-b",
        "GRI 403-2-d",
        "GRI 403-3-a",
        "GRI 403-4-a",
        "GRI 403-4-b",
        "GRI 403-5-a",
        "GRI 403-6-a",
        "GRI 403-6-b",
        "GRI 403-7-a",
        "GRI 403-9-c-i",
        "GRI 403-9-c-iii",
        "GRI 403-10-c-iii",
    }
    coverage_kpi_items = {
        "GRI 403-8-a",
        "GRI 403-8-a-i",
        "GRI 403-8-a-iii",
    }

    for requirement_id in sorted(management_items | coverage_kpi_items):
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.OHS_MANAGEMENT
        expected_kind = EvidenceKind.KPI_VALUE if requirement_id in coverage_kpi_items else EvidenceKind.MANAGEMENT_MECHANISM
        assert expected_kind in contract.evidence_kinds
        assert contract.verdict is None
        assert contract.review_status is None


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


def test_water_contracts_have_ontology_metadata():
    management_items = {
        "GRI 303-1-a",
        "GRI 303-1-b",
        "GRI 303-1-c",
        "GRI 303-1-d",
        "GRI 303-2-a",
        "GRI 303-2-a-ii",
    }
    kpi_items = {
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

    for requirement_id in sorted(management_items | kpi_items):
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.WATER_KPI
        assert contract.facets == (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,)
        expected_kind = EvidenceKind.MANAGEMENT_MECHANISM if requirement_id in management_items else EvidenceKind.KPI_VALUE
        assert contract.evidence_kinds == (expected_kind,)
        assert contract.verdict is None
        assert contract.review_status is None


def test_waste_contracts_have_ontology_metadata():
    management_items = {
        "GRI 306-1-a",
        "GRI 306-1-a-i",
        "GRI 306-1-a-ii",
        "GRI 306-2-a",
        "GRI 306-2-b",
        "GRI 306-4-b-i",
        "GRI 306-4-c-i",
    }
    kpi_items = {
        "GRI 306-3-a",
        "GRI 306-4-a",
        "GRI 306-4-b",
        "GRI 306-4-c",
    }

    for requirement_id in sorted(management_items | kpi_items):
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.WASTE_KPI
        assert contract.facets == (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,)
        expected_kind = EvidenceKind.MANAGEMENT_MECHANISM if requirement_id in management_items else EvidenceKind.KPI_VALUE
        assert contract.evidence_kinds == (expected_kind,)
        assert contract.verdict is None
        assert contract.review_status is None


def test_employee_and_benefits_contracts_have_ontology_metadata():
    employee_cases = {
        "GRI 401-1-a": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_REGION_BREAKDOWN},
            {EvidenceKind.KPI_BREAKDOWN},
        ),
        "GRI 401-1-b": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_REGION_BREAKDOWN},
            {EvidenceKind.KPI_BREAKDOWN},
        ),
        "GRI 401-3-c": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_GENDER_BREAKDOWN},
            {EvidenceKind.KPI_BREAKDOWN},
        ),
        "GRI 401-3-d": (
            {RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_GENDER_BREAKDOWN},
            {EvidenceKind.KPI_BREAKDOWN},
        ),
        "GRI 401-3-e": (
            {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_GENDER_BREAKDOWN},
            {EvidenceKind.KPI_VALUE},
        ),
    }
    benefits_items = {
        "GRI 401-2-a",
        "GRI 401-2-a-ii",
        "GRI 401-2-a-iv",
        "GRI 401-2-a-vii",
    }

    for requirement_id, (expected_facets, expected_evidence_kinds) in employee_cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.EMPLOYEE_KPI
        assert set(contract.facets) == expected_facets
        assert set(contract.evidence_kinds) == expected_evidence_kinds
        assert contract.verdict is None
        assert contract.review_status is None

    for requirement_id in benefits_items:
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.BENEFITS_POLICY
        assert set(contract.facets) == {
            RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN,
            RequirementFacet.REQUIRES_REGION_BREAKDOWN,
        }
        assert contract.evidence_kinds == (EvidenceKind.POLICY,)
        assert contract.verdict is None
        assert contract.review_status is None


def test_human_rights_policy_contracts_have_ontology_metadata():
    cases = {
        "GRI 407-1-b": {EvidenceKind.MANAGEMENT_MECHANISM},
        "GRI 408-1-a": {EvidenceKind.POLICY, EvidenceKind.MANAGEMENT_MECHANISM},
        "GRI 408-1-a-i": {EvidenceKind.POLICY},
        "GRI 408-1-a-ii": {EvidenceKind.POLICY, EvidenceKind.MANAGEMENT_MECHANISM},
        "GRI 408-1-c": {EvidenceKind.POLICY, EvidenceKind.MANAGEMENT_MECHANISM},
        "GRI 409-1-a": {EvidenceKind.POLICY, EvidenceKind.MANAGEMENT_MECHANISM},
        "GRI 409-1-b": {EvidenceKind.POLICY, EvidenceKind.MANAGEMENT_MECHANISM},
    }

    for requirement_id, expected_evidence_kinds in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.HUMAN_RIGHTS_POLICY
        assert RequirementFacet.REQUIRES_RISK_LOCATION in contract.facets
        assert set(contract.evidence_kinds) == expected_evidence_kinds
        assert contract.verdict is None
        assert contract.review_status is None


def test_residual_evidence_backed_contracts_have_ontology_metadata():
    cases = {
        "GRI 308-2-d": (
            SemanticGroup.SUPPLIER_ASSESSMENT,
            {RequirementFacet.REQUIRES_PERCENTAGE},
            {EvidenceKind.KPI_VALUE},
        ),
        "GRI 402-1-a": (
            SemanticGroup.NOTICE_PERIOD,
            {RequirementFacet.REQUIRES_COUNT},
            {EvidenceKind.KPI_VALUE},
        ),
        "GRI 404-2-a": (
            SemanticGroup.TRAINING_PROGRAM,
            {RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 406-1-a": (
            SemanticGroup.ZERO_EVENT_COMPLIANCE,
            {RequirementFacet.REQUIRES_COUNT},
            {EvidenceKind.EXPLICIT_ZERO_STATEMENT},
        ),
        "GRI 413-1-a": (
            SemanticGroup.COMMUNITY_PROGRAM,
            {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_IMPACT_TYPE},
            {EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 413-1-a-iv": (
            SemanticGroup.COMMUNITY_PROGRAM,
            {RequirementFacet.REQUIRES_PERCENTAGE},
            {EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 413-1-a-v": (
            SemanticGroup.COMMUNITY_PROGRAM,
            {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 414-2-d": (
            SemanticGroup.SUPPLIER_ASSESSMENT,
            {RequirementFacet.REQUIRES_PERCENTAGE},
            {EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 417-1-a": (
            SemanticGroup.PRODUCT_INFORMATION,
            {RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 417-1-a-ii": (
            SemanticGroup.PRODUCT_INFORMATION,
            {RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 417-1-a-iii": (
            SemanticGroup.PRODUCT_INFORMATION,
            {RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION},
            {EvidenceKind.MANAGEMENT_MECHANISM},
        ),
        "GRI 418-1-b": (
            SemanticGroup.PRIVACY_MANAGEMENT,
            {RequirementFacet.REQUIRES_COUNT},
            {EvidenceKind.MANAGEMENT_MECHANISM, EvidenceKind.EXPLICIT_ZERO_STATEMENT},
        ),
    }

    for requirement_id, (expected_group, expected_facets, expected_evidence_kinds) in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is expected_group
        assert set(contract.facets) == expected_facets
        assert set(contract.evidence_kinds) == expected_evidence_kinds
        assert contract.verdict is None
        assert contract.review_status is None
