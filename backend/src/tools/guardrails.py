from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus
from src.domain.models import DisclosureAssessment, DisclosureTask, EvidenceItem


def build_guarded_assessment(
    task: DisclosureTask,
    evidence: list[EvidenceItem],
    model_called: bool,
    verdict: AssessmentVerdict | None = None,
    rationale: str | None = None,
    missing_items: list[str] | None = None,
) -> DisclosureAssessment:
    _mark_low_text_assurance_evidence(task, evidence)

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
            missing_items=missing_items or [],
            model_called=model_called,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        )

    fallback_only = all(item.metadata.get("retrieval_strategy") == "global_fallback" for item in evidence)
    if fallback_only:
        return DisclosureAssessment(
            assessment_id=f"assessment:{task.task_id}",
            run_id=task.run_id,
            report_id=task.report_id,
            standard_id=task.standard_id,
            standard_version=task.standard_version,
            disclosure_id=task.disclosure_id,
            requirement_id=task.requirement_id,
            verdict=AssessmentVerdict.UNKNOWN,
            rationale=rationale or "Only global fallback evidence was found; bounded report evidence is required.",
            evidence=evidence,
            missing_items=missing_items or ["bounded report evidence"],
            model_called=model_called,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        )

    review_status = ReviewStatus.NOT_REQUIRED
    if verdict in {AssessmentVerdict.UNKNOWN, AssessmentVerdict.PARTIALLY_DISCLOSED}:
        review_status = ReviewStatus.NEEDS_MANUAL_REVIEW
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
        missing_items=missing_items or [],
        model_called=model_called,
        review_status=review_status,
    )


def _mark_low_text_assurance_evidence(task: DisclosureTask, evidence: list[EvidenceItem]) -> None:
    if not task.requirement_id.startswith("GRI 2-5"):
        return

    assurance_terms = ("鉴证报告", "独立有限鉴证", "有限保证", "assurance")
    for item in evidence:
        source_text = item.source_text.strip()
        source_text_lower = source_text.lower()
        has_assurance_term = any(term in source_text for term in assurance_terms[:-1]) or "assurance" in source_text_lower
        if has_assurance_term and len(source_text) < 120:
            item.needs_ocr_or_vlm = True
            item.requires_ocr = True
            item.requires_vlm = False
            item.ocr_or_vlm_reason = "assurance_page_text_too_short"
            for flag in (PageQualityFlag.SHORT_TEXT, PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED):
                if flag not in item.quality_flags:
                    item.quality_flags.append(flag)
