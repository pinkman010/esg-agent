from src.agents.disclosure_agent import DisclosureAgent
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus
from src.domain.models import DisclosureTask, DocumentChunk


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


def test_disclosure_agent_generates_assessment_from_evidence_without_model_call():
    chunk = DocumentChunk(
        chunk_id="chunk-1",
        report_id="report-1",
        text="Energy consumption is disclosed.",
        source_page=4,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(make_task(), [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.model_called is False
    assert result.assessment.evidence[0].source_page == 4
    assert result.recommendations == []


def test_disclosure_agent_marks_missing_evidence_for_manual_review_and_recommendation():
    result = DisclosureAgent().analyze(make_task(), [], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.recommendations[0].requirement_id == "GRI 302-1-a"


def test_disclosure_agent_uses_database_safe_recommendation_id_for_long_task_id():
    task = DisclosureTask(
        task_id="run-7170e39a373d48ad9d435912ae53bf0d:GRI 2-2-c-iii",
        run_id="run-7170e39a373d48ad9d435912ae53bf0d",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-2",
        requirement_id="GRI 2-2-c-iii",
        requirement_text="whether and how the approach differs across disclosures.",
        keywords=["approach", "differs", "disclosures"],
    )

    result = DisclosureAgent().analyze(task, [], confirm_llm=False)

    assert result.recommendations[0].recommendation_id.startswith("recommendation-")
    assert len(result.recommendations[0].recommendation_id) <= 64
