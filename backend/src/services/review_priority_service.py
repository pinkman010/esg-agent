from dataclasses import dataclass, field

from src.domain.enums import (
    ApplicabilityStatus,
    AssessmentVerdict,
    EvidenceStatus,
    PageQualityFlag,
    RiskLevel,
)
from src.domain.models import DisclosureAssessment
from src.domain.versions import CURRENT_RISK_RULE_VERSION


RISK_V2_RULE_VERSION = CURRENT_RISK_RULE_VERSION

NON_SUBSTANTIVE_EVIDENCE_TYPES = frozenset({"omission_note", "index_statement"})
POSITIVE_DISCLOSURE_VERDICTS = frozenset(
    {AssessmentVerdict.DISCLOSED, AssessmentVerdict.PARTIALLY_DISCLOSED}
)
SEVERE_QUALITY_FLAGS = frozenset(
    {
        PageQualityFlag.SCANNED,
        PageQualityFlag.LOW_TEXT_DENSITY,
        PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED,
        PageQualityFlag.OCR_FAILED,
        PageQualityFlag.NEEDS_MANUAL_REVIEW,
    }
)


@dataclass(frozen=True)
class ReviewPriorityContext:
    verdict: AssessmentVerdict
    has_evidence: bool
    evidence_types: frozenset[str] = field(default_factory=frozenset)
    applicability_status: ApplicabilityStatus = ApplicabilityStatus.UNDETERMINED
    analysis_failed: bool = False
    evidence_invalidated: bool = False
    page_conflict: bool = False
    source_conflict: bool = False
    severe_quality_anomaly: bool = False
    quality_warning: bool = False
    reopened: bool = False
    formal_output_exception: bool = False


@dataclass(frozen=True)
class ReviewPriorityClassification:
    review_priority: RiskLevel
    evidence_status: EvidenceStatus
    applicability_status: ApplicabilityStatus
    reason_codes: tuple[str, ...]
    risk_rule_version: str = RISK_V2_RULE_VERSION


def classify_review_priority(context: ReviewPriorityContext) -> ReviewPriorityClassification:
    evidence_status = _evidence_status(context)
    reasons = _descriptive_reasons(context, evidence_status)

    high_reasons: list[str] = []
    if context.analysis_failed:
        high_reasons.append("analysis_failed")
    if context.evidence_invalidated:
        high_reasons.append("evidence_invalidated")
    if context.page_conflict:
        high_reasons.append("page_conflict")
    if context.source_conflict:
        high_reasons.append("source_conflict")
    if context.severe_quality_anomaly:
        high_reasons.append("severe_evidence_quality")
    if context.reopened:
        high_reasons.append("reopened_for_review")
    if context.formal_output_exception:
        high_reasons.append("formal_output_exception")

    has_sufficiency_conflict = (
        context.applicability_status is not ApplicabilityStatus.NOT_APPLICABLE_CONFIRMED
        and context.verdict in POSITIVE_DISCLOSURE_VERDICTS
        and (
            not context.has_evidence
            or (
                bool(context.evidence_types)
                and context.evidence_types.issubset(NON_SUBSTANTIVE_EVIDENCE_TYPES)
            )
        )
    )
    if has_sufficiency_conflict:
        high_reasons.append("sufficiency_conflict")
        evidence_status = EvidenceStatus.CONFLICT

    if high_reasons:
        return _classification(
            RiskLevel.HIGH,
            evidence_status,
            context.applicability_status,
            [*reasons, *high_reasons],
        )

    if context.applicability_status is ApplicabilityStatus.NOT_APPLICABLE_CONFIRMED:
        return _classification(
            RiskLevel.LOW,
            evidence_status,
            context.applicability_status,
            [*reasons, "applicability_confirmed"],
        )

    if context.applicability_status is ApplicabilityStatus.NOT_APPLICABLE_CLAIMED:
        return _classification(
            RiskLevel.MEDIUM,
            evidence_status,
            context.applicability_status,
            [*reasons, "applicability_confirmation_required"],
        )

    if context.quality_warning:
        priority = RiskLevel.MEDIUM
    elif context.verdict is AssessmentVerdict.UNKNOWN:
        priority = (
            RiskLevel.LOW
            if evidence_status is EvidenceStatus.MISSING
            else RiskLevel.MEDIUM
        )
    elif context.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED:
        reasons.append("partial_disclosure")
        priority = RiskLevel.LOW
    elif context.verdict is AssessmentVerdict.NOT_DISCLOSED:
        reasons.append("not_disclosed")
        priority = RiskLevel.MEDIUM
    else:
        reasons.append("direct_disclosure_evidence")
        priority = RiskLevel.LOW

    return _classification(
        priority,
        evidence_status,
        context.applicability_status,
        reasons,
    )


def build_review_priority_context(
    assessment: DisclosureAssessment,
    *,
    applicability_status: ApplicabilityStatus | None = None,
    analysis_failed: bool = False,
    evidence_invalidated: bool = False,
    page_conflict: bool = False,
    source_conflict: bool = False,
    reopened: bool = False,
    formal_output_exception: bool = False,
) -> ReviewPriorityContext:
    evidence_types = frozenset(
        str(item.metadata.get("evidence_type", "substantive"))
        for item in assessment.evidence
    )
    severe_quality_anomaly = any(
        item.requires_ocr
        or item.requires_vlm
        or item.needs_ocr_or_vlm
        or bool(set(item.quality_flags).intersection(SEVERE_QUALITY_FLAGS))
        for item in assessment.evidence
    )
    quality_warning = any(
        bool(item.metadata.get("evidence_quality_warning"))
        for item in assessment.evidence
    )
    derived_page_conflict = page_conflict or any(
        bool(item.metadata.get("page_conflict"))
        for item in assessment.evidence
    )
    derived_source_conflict = source_conflict or any(
        bool(item.metadata.get("source_conflict"))
        for item in assessment.evidence
    )
    if applicability_status is None:
        has_substantive_evidence = bool(evidence_types.difference(NON_SUBSTANTIVE_EVIDENCE_TYPES))
        if assessment.verdict in POSITIVE_DISCLOSURE_VERDICTS or has_substantive_evidence:
            applicability_status = ApplicabilityStatus.APPLICABLE
        else:
            applicability_status = ApplicabilityStatus.UNDETERMINED

    return ReviewPriorityContext(
        verdict=assessment.verdict,
        has_evidence=bool(assessment.evidence),
        evidence_types=evidence_types,
        applicability_status=applicability_status,
        analysis_failed=analysis_failed,
        evidence_invalidated=evidence_invalidated,
        page_conflict=derived_page_conflict,
        source_conflict=derived_source_conflict,
        severe_quality_anomaly=severe_quality_anomaly,
        quality_warning=quality_warning,
        reopened=reopened,
        formal_output_exception=formal_output_exception,
    )


def _evidence_status(context: ReviewPriorityContext) -> EvidenceStatus:
    if context.evidence_invalidated:
        return EvidenceStatus.INVALID
    if context.page_conflict or context.source_conflict:
        return EvidenceStatus.CONFLICT
    if context.severe_quality_anomaly or context.quality_warning:
        return EvidenceStatus.QUALITY_WARNING
    if not context.has_evidence:
        return EvidenceStatus.MISSING
    if context.evidence_types and context.evidence_types.issubset(NON_SUBSTANTIVE_EVIDENCE_TYPES):
        return EvidenceStatus.NON_SUBSTANTIVE_ONLY
    return EvidenceStatus.VALID_DIRECT


def _descriptive_reasons(
    context: ReviewPriorityContext,
    evidence_status: EvidenceStatus,
) -> list[str]:
    reasons: list[str] = []
    if context.verdict is AssessmentVerdict.UNKNOWN:
        reasons.append("unknown_verdict")
    if evidence_status is EvidenceStatus.MISSING and (
        context.applicability_status is not ApplicabilityStatus.NOT_APPLICABLE_CONFIRMED
    ):
        reasons.append("no_valid_evidence")
    if evidence_status is EvidenceStatus.NON_SUBSTANTIVE_ONLY:
        reasons.append("non_substantive_evidence_only")
    if context.quality_warning:
        reasons.append("evidence_quality_warning")
    return reasons


def _classification(
    priority: RiskLevel,
    evidence_status: EvidenceStatus,
    applicability_status: ApplicabilityStatus,
    reason_codes: list[str],
) -> ReviewPriorityClassification:
    return ReviewPriorityClassification(
        review_priority=priority,
        evidence_status=evidence_status,
        applicability_status=applicability_status,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
    )
