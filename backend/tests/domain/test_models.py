import pytest
from pydantic import ValidationError

from src.domain.ai_models import AIAssessmentSuggestion
from src.domain.enums import (
    AISuggestionStatus,
    ApplicabilityStatus,
    AssessmentVerdict,
    EvidenceSourceMethod,
    EvidenceStatus,
    ReviewOperation,
    ReviewStatus,
    RiskLevel,
)
from src.domain.models import (
    AssessmentRisk,
    DisclosureAssessment,
    DisclosureTask,
    EvidenceItem,
    ReviewSnapshot,
)


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


def test_evidence_item_defaults_source_pdf_page_from_legacy_source_page():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="独立有限鉴证报告",
        source_page=77,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
    )

    assert evidence.source_page == 77
    assert evidence.source_pdf_page == 77
    assert evidence.source_report_page is None
    assert evidence.needs_ocr_or_vlm is False
    assert evidence.requires_ocr is False
    assert evidence.requires_vlm is False
    assert evidence.ocr_or_vlm_reason is None
    assert evidence.evidence_preview == "独立有限鉴证报告"


def test_evidence_item_builds_short_preview_from_source_text():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="A" * 260,
        source_page=77,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
    )

    assert evidence.evidence_preview == f"{'A' * 200}..."


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
    assert task.candidate_pdf_pages == [6]
    assert task.candidate_page_source == "gri_report_index"
    assert task.index_page == 71


def test_disclosure_task_can_carry_candidate_pdf_and_report_pages():
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
        candidate_pages=[1, 3, 6],
        candidate_pdf_pages=[1, 3, 6],
        candidate_report_pages=[None, 2, 5],
        candidate_page_source="gri_report_index",
        index_page=71,
    )

    assert task.candidate_pages == [1, 3, 6]
    assert task.candidate_pdf_pages == [1, 3, 6]
    assert task.candidate_report_pages == [None, 2, 5]


def test_risk_v2_1_dimensions_are_explicit_and_legacy_risk_defaults_remain_compatible():
    legacy = AssessmentRisk(
        risk_id="risk-v1",
        assessment_id="assessment-1",
        risk_level=RiskLevel.HIGH,
        reason_codes=["unknown_verdict"],
        risk_rule_version="risk-v1",
        trigger_event="analysis_completed",
    )
    current = AssessmentRisk(
        risk_id="risk-v2-1",
        assessment_id="assessment-1",
        risk_level=RiskLevel.LOW,
        reason_codes=["unknown_verdict", "no_valid_evidence"],
        risk_rule_version="risk-v2.1",
        trigger_event="analysis_completed",
        evidence_status=EvidenceStatus.MISSING,
        applicability_status=ApplicabilityStatus.UNDETERMINED,
    )

    assert legacy.evidence_status is None
    assert legacy.applicability_status is None
    assert current.evidence_status is EvidenceStatus.MISSING
    assert current.applicability_status is ApplicabilityStatus.UNDETERMINED


def test_review_snapshot_can_append_an_independent_applicability_decision():
    snapshot = ReviewSnapshot(
        snapshot_id="snapshot-1",
        assessment_id="assessment-1",
        run_id="run-1",
        sequence=1,
        operation_type=ReviewOperation.MODIFY,
        reviewer_name="张三",
        reason_code="applicability_reviewed",
        reviewed_applicability_status=ApplicabilityStatus.APPLICABLE,
    )

    assert snapshot.reviewed_applicability_status is ApplicabilityStatus.APPLICABLE


def test_ai_assessment_suggestion_is_append_only_advice_without_review_authority():
    suggestion = AIAssessmentSuggestion(
        suggestion_id="ai-suggestion-1",
        assessment_id="assessment-1",
        run_id="run-1",
        status=AISuggestionStatus.SUCCEEDED,
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="deepseek-gri-assist-v1",
        input_hash="a" * 64,
        suggested_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
        rationale_zh="存在部分直接证据，仍缺少范围说明。",
        missing_items_zh=["范围说明"],
        evidence_ids=["evidence-1"],
        evidence_pdf_pages=[41],
        confidence=0.78,
        guardrail_codes=[],
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )

    assert suggestion.review_status is None
    assert "review_status" not in suggestion.model_dump()
    assert "applicability_status" not in suggestion.model_dump()
