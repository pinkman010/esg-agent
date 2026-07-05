import pytest

from src.standards.evidence_ontology import EvidenceKind, RequirementFacet
from src.standards.no_evidence_guardrails import (
    NoEvidenceGuardrailCategory,
    get_no_evidence_guardrail,
)


def test_get_no_evidence_guardrail_returns_incident_classification_rule():
    guardrail = get_no_evidence_guardrail("GRI 416-2-a-i")

    assert guardrail is not None
    assert guardrail.requirement_id == "GRI 416-2-a-i"
    assert guardrail.category is NoEvidenceGuardrailCategory.INCIDENT_CLASSIFICATION
    assert RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION in guardrail.required_facets
    assert EvidenceKind.EXPLICIT_ZERO_STATEMENT in guardrail.forbidden_evidence_kinds
    assert "罚款或处罚事件数量" in guardrail.missing_items


@pytest.mark.parametrize(
    "requirement_id",
    [
        "GRI 406-1-b",
        "GRI 406-1-b-i",
        "GRI 406-1-b-ii",
        "GRI 406-1-b-iii",
        "GRI 406-1-b-iv",
        "GRI 416-2-a-i",
        "GRI 416-2-a-ii",
        "GRI 416-2-a-iii",
        "GRI 417-2-a",
        "GRI 417-2-a-i",
        "GRI 417-2-a-ii",
        "GRI 417-2-a-iii",
        "GRI 417-2-b",
        "GRI 417-3-a",
        "GRI 417-3-a-i",
        "GRI 417-3-a-ii",
        "GRI 417-3-a-iii",
        "GRI 417-3-b",
        "GRI 418-1-a-i",
        "GRI 418-1-a-ii",
    ],
)
def test_zero_event_classification_guardrails_are_registered(requirement_id):
    guardrail = get_no_evidence_guardrail(requirement_id)

    assert guardrail is not None
    assert guardrail.category is NoEvidenceGuardrailCategory.INCIDENT_CLASSIFICATION
    assert guardrail.missing_items
    assert guardrail.rationale


@pytest.mark.parametrize(
    "requirement_id",
    [
        "GRI 407-1-a",
        "GRI 407-1-a-i",
        "GRI 407-1-a-ii",
        "GRI 408-1-b",
        "GRI 408-1-b-i",
        "GRI 408-1-b-ii",
        "GRI 409-1-a-i",
        "GRI 409-1-a-ii",
        "GRI 413-2-a",
        "GRI 413-2-a-i",
        "GRI 413-2-a-ii",
    ],
)
def test_risk_location_guardrails_are_registered(requirement_id):
    guardrail = get_no_evidence_guardrail(requirement_id)

    assert guardrail is not None
    assert guardrail.category is NoEvidenceGuardrailCategory.RISK_LOCATION
    assert RequirementFacet.REQUIRES_RISK_LOCATION in guardrail.required_facets
    assert guardrail.forbidden_evidence_kinds
    assert guardrail.missing_items


@pytest.mark.parametrize(
    "requirement_id",
    [
        "GRI 305-2-c",
        "GRI 305-2-d",
        "GRI 305-2-d-i",
        "GRI 305-7-a",
        "GRI 403-9-f",
        "GRI 403-9-g",
        "GRI 403-10-d",
        "GRI 403-10-e",
    ],
)
def test_method_scope_guardrails_are_registered(requirement_id):
    guardrail = get_no_evidence_guardrail(requirement_id)

    assert guardrail is not None
    assert guardrail.category is NoEvidenceGuardrailCategory.METHOD_SCOPE
    assert RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION in guardrail.required_facets
    assert EvidenceKind.KPI_VALUE in guardrail.forbidden_evidence_kinds
    assert guardrail.missing_items


@pytest.mark.parametrize(
    "requirement_id",
    [
        "GRI 402-1-b",
        "GRI 403-1-a-i",
        "GRI 403-2-c",
        "GRI 403-8-a-ii",
        "GRI 403-8-b",
        "GRI 403-8-c",
        "GRI 403-9-a-iv",
        "GRI 403-9-b-iv",
        "GRI 403-9-c-ii",
        "GRI 403-10-a-iii",
        "GRI 403-10-b-iii",
        "GRI 403-10-c-ii",
        "GRI 404-1-a-i",
        "GRI 404-1-a-ii",
        "GRI 404-2-b",
        "GRI 405-2-b",
        "GRI 410-1-a",
        "GRI 410-1-b",
        "GRI 413-1-a-i",
        "GRI 413-1-a-ii",
        "GRI 413-1-a-iii",
        "GRI 413-1-a-vi",
        "GRI 413-1-a-vii",
        "GRI 413-1-a-viii",
        "GRI 416-1-a",
        "GRI 417-1-a-i",
        "GRI 417-1-a-iv",
        "GRI 417-1-a-v",
        "GRI 417-1-b",
    ],
)
def test_remaining_no_evidence_guardrails_are_registered(requirement_id):
    guardrail = get_no_evidence_guardrail(requirement_id)

    assert guardrail is not None
    assert guardrail.missing_items
    assert guardrail.rationale
