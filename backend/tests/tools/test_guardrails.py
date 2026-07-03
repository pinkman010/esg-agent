from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus
from src.domain.models import DisclosureTask, EvidenceItem
from src.tools.guardrails import build_guarded_assessment


def make_task():
    return DisclosureTask(
        task_id="task-1",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 302",
        requirement_id="GRI 302-1-a",
        requirement_text="Disclose energy consumption.",
        keywords=["energy"],
    )


def test_no_evidence_forces_unknown_and_manual_review():
    assessment = build_guarded_assessment(make_task(), evidence=[], model_called=False)

    assert assessment.verdict is AssessmentVerdict.UNKNOWN
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW


def test_ocr_kpi_evidence_forces_manual_review():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="Energy consumption: 100 MWh",
        source_page=3,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.OCR,
        is_kpi_evidence=True,
    )

    assessment = build_guarded_assessment(make_task(), evidence=[evidence], model_called=False)

    assert assessment.verdict is AssessmentVerdict.DISCLOSED
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW


def test_global_fallback_evidence_forces_manual_review():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="Legal name appears outside candidate pages.",
        source_page=10,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        metadata={"retrieval_strategy": "global_fallback"},
    )

    assessment = build_guarded_assessment(make_task(), evidence=[evidence], model_called=False)

    assert assessment.verdict is AssessmentVerdict.DISCLOSED
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW


def test_complex_table_evidence_forces_manual_review():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="KPI table text.",
        source_page=64,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    assessment = build_guarded_assessment(make_task(), evidence=[evidence], model_called=False)

    assert assessment.verdict is AssessmentVerdict.DISCLOSED
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
