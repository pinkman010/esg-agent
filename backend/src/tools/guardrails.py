from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus
from src.domain.models import DisclosureAssessment, DisclosureTask, EvidenceItem


def build_guarded_assessment(
    task: DisclosureTask,
    evidence: list[EvidenceItem],
    model_called: bool,
    verdict: AssessmentVerdict | None = None,
    rationale: str | None = None,
) -> DisclosureAssessment:
    if not evidence:
        return DisclosureAssessment(
            assessment_id=f"assessment:{task.task_id}",
            run_id=task.run_id,
            report_id=task.report_id,
            standard_id=task.standard_id,
            standard_version=task.standard_version,
            disclosure_id=task.disclosure_id,
            requirement_id=task.requirement_id,
            verdict=AssessmentVerdict.UNKNOWN,
            rationale=rationale or "No report evidence was found for this requirement.",
            evidence=[],
            model_called=model_called,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        )

    review_status = ReviewStatus.NOT_REQUIRED
    if any(item.is_kpi_evidence and item.source_method in {EvidenceSourceMethod.OCR, EvidenceSourceMethod.VLM} for item in evidence):
        review_status = ReviewStatus.NEEDS_MANUAL_REVIEW
    if any(item.metadata.get("retrieval_strategy") in {"global_fallback", "global_no_index"} for item in evidence):
        review_status = ReviewStatus.NEEDS_MANUAL_REVIEW
    manual_review_flags = {
        PageQualityFlag.LOW_TEXT_DENSITY,
        PageQualityFlag.SCANNED,
        PageQualityFlag.COMPLEX_TABLE,
    }
    if any(any(flag in manual_review_flags for flag in item.quality_flags) for item in evidence):
        review_status = ReviewStatus.NEEDS_MANUAL_REVIEW

    return DisclosureAssessment(
        assessment_id=f"assessment:{task.task_id}",
        run_id=task.run_id,
        report_id=task.report_id,
        standard_id=task.standard_id,
        standard_version=task.standard_version,
        disclosure_id=task.disclosure_id,
        requirement_id=task.requirement_id,
        verdict=verdict or AssessmentVerdict.DISCLOSED,
        rationale=rationale or "Evidence was found for this requirement.",
        evidence=evidence,
        model_called=model_called,
        review_status=review_status,
    )
