import pytest

from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus
from src.domain.models import DisclosureAssessment, EvidenceItem


def _risk_v2_api():
    try:
        from src.domain.enums import ApplicabilityStatus, EvidenceStatus, RiskLevel
        from src.services.review_priority_service import (
            RISK_V2_RULE_VERSION,
            ReviewPriorityContext,
            build_review_priority_context,
            classify_review_priority,
        )
    except ImportError as exc:
        pytest.fail(f"risk-v2 classification API is not implemented: {exc}")
    return {
        "ApplicabilityStatus": ApplicabilityStatus,
        "EvidenceStatus": EvidenceStatus,
        "RiskLevel": RiskLevel,
        "RISK_V2_RULE_VERSION": RISK_V2_RULE_VERSION,
        "ReviewPriorityContext": ReviewPriorityContext,
        "build_review_priority_context": build_review_priority_context,
        "classify_review_priority": classify_review_priority,
    }


def _context(**overrides):
    api = _risk_v2_api()
    values = {
        "verdict": AssessmentVerdict.UNKNOWN,
        "has_evidence": False,
        "evidence_types": frozenset(),
        "applicability_status": api["ApplicabilityStatus"].UNDETERMINED,
    }
    values.update(overrides)
    return api, api["ReviewPriorityContext"](**values)


@pytest.mark.parametrize(
    ("overrides", "expected_priority", "expected_evidence_status", "expected_reason"),
    [
        ({}, "low", "missing", "unknown_verdict"),
        (
            {"has_evidence": True, "evidence_types": frozenset({"index_statement"})},
            "medium",
            "non_substantive_only",
            "non_substantive_evidence_only",
        ),
        (
            {
                "verdict": AssessmentVerdict.PARTIALLY_DISCLOSED,
                "has_evidence": True,
                "evidence_types": frozenset({"substantive"}),
            },
            "low",
            "valid_direct",
            "partial_disclosure",
        ),
        (
            {
                "verdict": AssessmentVerdict.DISCLOSED,
                "has_evidence": True,
                "evidence_types": frozenset({"substantive"}),
            },
            "low",
            "valid_direct",
            "direct_disclosure_evidence",
        ),
        (
            {
                "verdict": AssessmentVerdict.DISCLOSED,
                "has_evidence": True,
                "evidence_types": frozenset({"omission_note"}),
            },
            "high",
            "conflict",
            "sufficiency_conflict",
        ),
        ({"evidence_invalidated": True}, "high", "invalid", "evidence_invalidated"),
        ({"page_conflict": True}, "high", "conflict", "page_conflict"),
        ({"source_conflict": True}, "high", "conflict", "source_conflict"),
        ({"analysis_failed": True}, "high", "missing", "analysis_failed"),
        ({"severe_quality_anomaly": True}, "high", "quality_warning", "severe_evidence_quality"),
        ({"quality_warning": True}, "medium", "quality_warning", "evidence_quality_warning"),
    ],
)
def test_risk_v2_rule_matrix(overrides, expected_priority, expected_evidence_status, expected_reason):
    api, context = _context(**overrides)

    result = api["classify_review_priority"](context)

    assert result.review_priority is api["RiskLevel"](expected_priority)
    assert result.evidence_status is api["EvidenceStatus"](expected_evidence_status)
    assert expected_reason in result.reason_codes
    assert result.risk_rule_version == api["RISK_V2_RULE_VERSION"] == "risk-v2.1"


def test_claimed_not_applicable_is_medium_and_confirmed_is_low():
    api, claimed = _context(
        applicability_status=_risk_v2_api()["ApplicabilityStatus"].NOT_APPLICABLE_CLAIMED
    )
    _, confirmed = _context(
        applicability_status=_risk_v2_api()["ApplicabilityStatus"].NOT_APPLICABLE_CONFIRMED
    )

    claimed_result = api["classify_review_priority"](claimed)
    confirmed_result = api["classify_review_priority"](confirmed)

    assert claimed_result.review_priority is api["RiskLevel"].MEDIUM
    assert claimed_result.applicability_status is api["ApplicabilityStatus"].NOT_APPLICABLE_CLAIMED
    assert "applicability_confirmation_required" in claimed_result.reason_codes
    assert confirmed_result.review_priority is api["RiskLevel"].LOW
    assert confirmed_result.applicability_status is api["ApplicabilityStatus"].NOT_APPLICABLE_CONFIRMED
    assert "applicability_confirmed" in confirmed_result.reason_codes


@pytest.mark.parametrize(
    ("overrides", "expected_priority"),
    [
        ({}, "low"),
        ({"has_evidence": True, "evidence_types": frozenset({"index_statement"})}, "medium"),
        ({"has_evidence": True, "evidence_types": frozenset({"omission_note"})}, "medium"),
        ({"quality_warning": True}, "medium"),
    ],
)
def test_unknown_is_never_high_without_an_explicit_anomaly(overrides, expected_priority):
    api, context = _context(**overrides)

    result = api["classify_review_priority"](context)

    assert result.review_priority is api["RiskLevel"](expected_priority)
    assert "unknown_verdict" in result.reason_codes


def test_unknown_without_evidence_keeps_undetermined_applicability_when_priority_is_low():
    api, context = _context()

    result = api["classify_review_priority"](context)

    assert result.review_priority is api["RiskLevel"].LOW
    assert result.evidence_status is api["EvidenceStatus"].MISSING
    assert result.applicability_status is api["ApplicabilityStatus"].UNDETERMINED
    assert result.reason_codes == ("unknown_verdict", "no_valid_evidence")


def _assessment(verdict, *, evidence_type="substantive", quality_flags=None, with_evidence=True):
    evidence = []
    if with_evidence:
        evidence = [
            EvidenceItem(
                evidence_id="evidence-1",
                run_id="run-1",
                report_id="report-1",
                source_text="Evidence",
                source_page=1,
                source_file_hash="hash-1",
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                quality_flags=quality_flags or [],
                metadata={"evidence_type": evidence_type},
            )
        ]
    return DisclosureAssessment(
        assessment_id="assessment-1",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        verdict=verdict,
        rationale="rationale",
        evidence=evidence,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
    )


def test_build_context_infers_applicability_and_severe_quality_without_mutating_assessment():
    api = _risk_v2_api()
    disclosed = _assessment(AssessmentVerdict.DISCLOSED)
    unknown = _assessment(AssessmentVerdict.UNKNOWN, with_evidence=False)
    quality = _assessment(
        AssessmentVerdict.UNKNOWN,
        quality_flags=[PageQualityFlag.NEEDS_MANUAL_REVIEW],
    )

    disclosed_context = api["build_review_priority_context"](disclosed)
    unknown_context = api["build_review_priority_context"](unknown)
    quality_context = api["build_review_priority_context"](quality)

    assert disclosed_context.applicability_status is api["ApplicabilityStatus"].APPLICABLE
    assert unknown_context.applicability_status is api["ApplicabilityStatus"].UNDETERMINED
    assert quality_context.severe_quality_anomaly is True
    assert disclosed.evidence[0].metadata == {"evidence_type": "substantive"}
