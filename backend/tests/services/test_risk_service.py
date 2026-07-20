from unittest.mock import Mock

from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus, RiskLevel
from src.domain.models import DisclosureAssessment, EvidenceItem
from src.services.risk_service import (
    RISK_RULE_VERSION,
    calculate_and_store_risk,
    classify_assessment_risk,
)


def assessment(verdict, *, evidence=True, quality_flags=None, evidence_type="substantive"):
    items = []
    if evidence:
        items = [
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
        evidence=items,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW if verdict is not AssessmentVerdict.DISCLOSED else ReviewStatus.NOT_REQUIRED,
    )


def test_risk_v1_classifies_high_medium_and_low_boundaries():
    unknown = classify_assessment_risk(assessment(AssessmentVerdict.UNKNOWN, evidence=False))
    low_quality = classify_assessment_risk(
        assessment(AssessmentVerdict.PARTIALLY_DISCLOSED, quality_flags=[PageQualityFlag.NEEDS_MANUAL_REVIEW])
    )
    omission = classify_assessment_risk(
        assessment(AssessmentVerdict.UNKNOWN, evidence_type="omission_note")
    )
    partial = classify_assessment_risk(assessment(AssessmentVerdict.PARTIALLY_DISCLOSED))
    disclosed = classify_assessment_risk(assessment(AssessmentVerdict.DISCLOSED))

    assert unknown.risk_level is RiskLevel.HIGH
    assert {"unknown_verdict", "no_valid_evidence"}.issubset(unknown.reason_codes)
    assert low_quality.risk_level is RiskLevel.HIGH
    assert "evidence_quality_risk" in low_quality.reason_codes
    assert omission.risk_level is RiskLevel.HIGH
    assert "non_substantive_evidence_only" in omission.reason_codes
    assert partial.risk_level is RiskLevel.MEDIUM
    assert disclosed.risk_level is RiskLevel.LOW
    assert RISK_RULE_VERSION == "risk-v1"


def test_calculate_and_store_risk_dispatches_explicit_risk_v2_1_without_changing_legacy_default():
    repo = Mock()
    repo.new_risk_id.side_effect = ["risk-current", "risk-legacy"]
    repo.save_assessment_risk.side_effect = lambda risk: risk
    unknown = assessment(AssessmentVerdict.UNKNOWN, evidence=False)

    current = calculate_and_store_risk(
        repo,
        unknown,
        trigger_event="analysis_completed",
        risk_rule_version="risk-v2.1",
    )
    legacy = calculate_and_store_risk(
        repo,
        unknown,
        trigger_event="legacy_caller",
    )

    assert current.risk_level is RiskLevel.LOW
    assert current.evidence_status.value == "missing"
    assert current.applicability_status.value == "undetermined"
    assert current.risk_rule_version == "risk-v2.1"
    assert legacy.risk_level is RiskLevel.HIGH
    assert legacy.evidence_status is None
    assert legacy.applicability_status is None
    assert legacy.risk_rule_version == "risk-v1"


def test_calculate_and_store_risk_rejects_unknown_rule_version():
    repo = Mock()

    try:
        calculate_and_store_risk(
            repo,
            assessment(AssessmentVerdict.DISCLOSED),
            trigger_event="analysis_completed",
            risk_rule_version="risk-future",
        )
    except ValueError as exc:
        assert str(exc) == "unsupported risk rule version: risk-future"
    else:
        raise AssertionError("unsupported risk version must be rejected")
