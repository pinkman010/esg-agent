from src.domain.enums import AssessmentVerdict, ReviewStatus
from src.standards.evidence_contracts import get_requirement_contract


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
