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


def make_task_with_requirement(**overrides):
    data = {
        "task_id": "task-1",
        "run_id": "run-1",
        "report_id": "report-1",
        "standard_id": "GRI 2",
        "standard_version": "2021",
        "disclosure_id": "GRI 2-5",
        "requirement_id": "GRI 2-5-b",
        "requirement_text": "describe external assurance.",
        "keywords": ["鉴证报告"],
    }
    data.update(overrides)
    return DisclosureTask(**data)


def test_no_evidence_forces_unknown_and_manual_review():
    assessment = build_guarded_assessment(make_task(), evidence=[], model_called=False)

    assert assessment.verdict is AssessmentVerdict.UNKNOWN
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW


def test_guardrails_marks_low_text_assurance_page_for_ocr_or_vlm():
    evidence = EvidenceItem(
        evidence_id="evidence-assurance",
        run_id="run-1",
        report_id="report-1",
        source_text="独立有限鉴证报告",
        source_page=77,
        source_pdf_page=77,
        source_report_page=76,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
    )

    assessment = build_guarded_assessment(
        make_task_with_requirement(),
        evidence=[evidence],
        model_called=False,
    )

    assert assessment.evidence[0].needs_ocr_or_vlm is True
    assert assessment.evidence[0].requires_ocr is True
    assert assessment.evidence[0].requires_vlm is False
    assert assessment.evidence[0].ocr_or_vlm_reason == "assurance_page_text_too_short"
    assert PageQualityFlag.SHORT_TEXT in assessment.evidence[0].quality_flags
    assert PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED in assessment.evidence[0].quality_flags


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

    assert assessment.verdict is AssessmentVerdict.UNKNOWN
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "bounded report evidence" in assessment.missing_items


def test_global_no_index_evidence_forces_unknown_and_manual_review():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="A keyword appears without profile or bounded candidate routing.",
        source_page=10,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        metadata={"retrieval_strategy": "global_no_index"},
    )

    assessment = build_guarded_assessment(make_task(), evidence=[evidence], model_called=False)

    assert assessment.verdict is AssessmentVerdict.UNKNOWN
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "routed or bounded report evidence" in assessment.missing_items


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


def test_explicit_unknown_with_candidate_evidence_forces_manual_review():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="Candidate page text is insufficient.",
        source_page=3,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        metadata={"retrieval_strategy": "index_page_bounded"},
    )

    assessment = build_guarded_assessment(
        make_task(),
        evidence=[evidence],
        model_called=False,
        verdict=AssessmentVerdict.UNKNOWN,
        missing_items=["specific disclosure detail"],
    )

    assert assessment.verdict is AssessmentVerdict.UNKNOWN
    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert assessment.missing_items == ["specific disclosure detail"]
