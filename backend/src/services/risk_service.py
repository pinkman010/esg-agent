from dataclasses import dataclass

from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, PageQualityFlag, RiskLevel
from src.domain.models import AssessmentRisk, DisclosureAssessment


RISK_RULE_VERSION = "risk-v1"


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
) -> AssessmentRisk:
    classification = classify_assessment_risk(assessment)
    risk = AssessmentRisk(
        risk_id=repo.new_risk_id(),
        assessment_id=assessment.assessment_id,
        snapshot_id=snapshot_id,
        risk_level=classification.risk_level,
        reason_codes=classification.reason_codes,
        risk_rule_version=RISK_RULE_VERSION,
        trigger_event=trigger_event,
    )
    return repo.save_assessment_risk(risk)
