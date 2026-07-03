import pytest
from pydantic import ValidationError

from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus
from src.domain.models import DisclosureAssessment, DisclosureTask, EvidenceItem


def make_evidence(**overrides):
    data = {
        "evidence_id": "evidence-1",
        "run_id": "run-1",
        "report_id": "report-1",
        "source_text": "The company discloses total energy consumption.",
        "source_page": 12,
        "source_file_hash": "abc123",
        "source_method": EvidenceSourceMethod.PDFPLUMBER,
    }
    data.update(overrides)
    return EvidenceItem(**data)


def make_assessment(**overrides):
    data = {
        "assessment_id": "assessment-1",
        "run_id": "run-1",
        "report_id": "report-1",
        "standard_id": "GRI",
        "standard_version": "2021",
        "disclosure_id": "GRI 302",
        "requirement_id": "GRI 302-1-a",
        "verdict": AssessmentVerdict.DISCLOSED,
        "rationale": "Evidence directly addresses the requirement.",
        "evidence": [make_evidence()],
        "model_called": False,
        "review_status": ReviewStatus.NOT_REQUIRED,
    }
    data.update(overrides)
    return DisclosureAssessment(**data)


def test_valid_assessment_with_evidence_keeps_traceability_fields():
    assessment = make_assessment()

    assert assessment.run_id == "run-1"
    assert assessment.report_id == "report-1"
    assert assessment.standard_id == "GRI"
    assert assessment.evidence[0].source_page == 12
    assert assessment.evidence[0].source_file_hash == "abc123"
    assert assessment.model_called is False
    assert assessment.review_status is ReviewStatus.NOT_REQUIRED


def test_non_unknown_verdict_without_evidence_is_rejected():
    with pytest.raises(ValidationError, match="evidence is required"):
        make_assessment(evidence=[])


def test_ocr_or_vlm_kpi_evidence_requires_manual_review():
    assessment = make_assessment(
        evidence=[
            make_evidence(
                source_method=EvidenceSourceMethod.OCR,
                is_kpi_evidence=True,
            )
        ],
        review_status=ReviewStatus.NOT_REQUIRED,
    )

    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW


def test_disclosure_task_can_carry_report_index_candidate_pages():
    task = DisclosureTask(
        task_id="run-1:GRI 2-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        requirement_text="report its legal name;",
        keywords=["legal", "name"],
        candidate_pages=[6],
        candidate_page_source="gri_report_index",
        index_page=71,
    )

    assert task.candidate_pages == [6]
    assert task.candidate_page_source == "gri_report_index"
    assert task.index_page == 71
