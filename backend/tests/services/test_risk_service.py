from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus, RiskLevel
from src.domain.models import DisclosureAssessment, EvidenceItem
from src.services.risk_service import classify_assessment_risk


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
