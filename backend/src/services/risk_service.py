from dataclasses import dataclass

from src.db.repositories import Repository
from src.domain.enums import ApplicabilityStatus, AssessmentVerdict, PageQualityFlag, RiskLevel
from src.domain.models import AssessmentRisk, DisclosureAssessment
from src.domain.versions import CURRENT_RISK_RULE_VERSION, LEGACY_RISK_RULE_VERSION
from src.services.review_priority_service import (
    build_review_priority_context,
    classify_review_priority,
)


RISK_RULE_VERSION = LEGACY_RISK_RULE_VERSION


@dataclass(frozen=True)
class RiskClassification:
    risk_level: RiskLevel
    reason_codes: list[str]


def classify_assessment_risk(assessment: DisclosureAssessment) -> RiskClassification:
    reasons: list[str] = []
    if assessment.verdict is AssessmentVerdict.UNKNOWN:
        reasons.append("unknown_verdict")
    if not assessment.evidence:
        reasons.append("no_valid_evidence")

    quality_risk_flags = {
        PageQualityFlag.SCANNED,
        PageQualityFlag.LOW_TEXT_DENSITY,
        PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED,
        PageQualityFlag.OCR_FAILED,
        PageQualityFlag.NEEDS_MANUAL_REVIEW,
    }
    if any(
        evidence.requires_ocr
        or evidence.requires_vlm
        or evidence.needs_ocr_or_vlm
        or bool(set(evidence.quality_flags).intersection(quality_risk_flags))
        for evidence in assessment.evidence
    ):
        reasons.append("evidence_quality_risk")

    evidence_types = {
        str(evidence.metadata.get("evidence_type", "substantive"))
        for evidence in assessment.evidence
    }
    if evidence_types and evidence_types.issubset({"omission_note", "index_statement"}):
        reasons.append("non_substantive_evidence_only")

    if reasons:
        return RiskClassification(RiskLevel.HIGH, reasons)
    if assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED:
        return RiskClassification(RiskLevel.MEDIUM, ["partial_disclosure"])
    return RiskClassification(RiskLevel.LOW, ["direct_disclosure_evidence"])


def calculate_and_store_risk(
    repo: Repository,
    assessment: DisclosureAssessment,
    *,
    trigger_event: str,
    snapshot_id: str | None = None,
    risk_rule_version: str = RISK_RULE_VERSION,
    applicability_status: ApplicabilityStatus | None = None,
    analysis_failed: bool = False,
    evidence_invalidated: bool = False,
    page_conflict: bool = False,
    source_conflict: bool = False,
    reopened: bool = False,
    formal_output_exception: bool = False,
    commit: bool = True,
) -> AssessmentRisk:
    evidence_status = None
    classified_applicability = None
    if risk_rule_version == LEGACY_RISK_RULE_VERSION:
        classification = classify_assessment_risk(assessment)
        risk_level = classification.risk_level
        reason_codes = classification.reason_codes
    elif risk_rule_version == CURRENT_RISK_RULE_VERSION:
        classification = classify_review_priority(
            build_review_priority_context(
                assessment,
                applicability_status=applicability_status,
                analysis_failed=analysis_failed,
                evidence_invalidated=evidence_invalidated,
                page_conflict=page_conflict,
                source_conflict=source_conflict,
                reopened=reopened,
                formal_output_exception=formal_output_exception,
            )
        )
        risk_level = classification.review_priority
        reason_codes = list(classification.reason_codes)
        evidence_status = classification.evidence_status
        classified_applicability = classification.applicability_status
    else:
        raise ValueError(f"unsupported risk rule version: {risk_rule_version}")

    risk = AssessmentRisk(
        risk_id=repo.new_risk_id(),
        assessment_id=assessment.assessment_id,
        snapshot_id=snapshot_id,
        risk_level=risk_level,
        reason_codes=reason_codes,
        risk_rule_version=risk_rule_version,
        evidence_status=evidence_status,
        applicability_status=classified_applicability,
        trigger_event=trigger_event,
    )
    if commit:
        return repo.save_assessment_risk(risk)
    return repo.save_assessment_risk(risk, commit=False)
