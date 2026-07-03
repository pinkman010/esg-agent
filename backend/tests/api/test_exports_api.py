import pytest

pytestmark = pytest.mark.anyio

from sqlalchemy import select

from src.db.models import AuditEventRecord
from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, EvidenceItem, Report, ReviewDecision


def seed_export_data(session):
    repo = Repository(session)
    repo.create_report(Report(report_id="report-1", original_filename="report.pdf", stored_path="x", file_hash="hash-1"))
    repo.create_run(AnalysisRun(run_id="run-1", report_id="report-1", status=RunStatus.COMPLETED))
    assessment = DisclosureAssessment(
        assessment_id="assessment-1",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 302",
        requirement_id="GRI 302-1-a",
        verdict=AssessmentVerdict.DISCLOSED,
        rationale="Evidence found.",
        evidence=[EvidenceItem(evidence_id="evidence-1", run_id="run-1", report_id="report-1", source_text="Energy", source_page=1, source_file_hash="hash-1", source_method=EvidenceSourceMethod.PDFPLUMBER)],
        review_status=ReviewStatus.NOT_REQUIRED,
    )
    repo.save_assessment(assessment)
    repo.save_evidence_item("assessment-1", assessment.evidence[0])
    repo.save_review_decision(ReviewDecision(decision_id="decision-1", run_id="run-1", assessment_id="assessment-1", review_status=ReviewStatus.APPROVED, reviewer_note="Checked."))


async def test_export_api_returns_json_and_csv(api_client, api_session):
    seed_export_data(api_session)

    assessments_json = await api_client.get("/api/exports/runs/run-1/assessments.json")
    assessments_csv = await api_client.get("/api/exports/runs/run-1/assessments.csv")
    review_json = await api_client.get("/api/exports/runs/run-1/review.json")
    review_csv = await api_client.get("/api/exports/runs/run-1/review.csv")

    assert assessments_json.status_code == 200
    assert assessments_json.json()[0]["assessment_id"] == "assessment-1"
    assert assessments_csv.status_code == 200
    assert "assessment_id" in assessments_csv.text
    assert review_json.json()[0]["decision_id"] == "decision-1"
    assert "decision_id" in review_csv.text
    event_types = api_session.scalars(
        select(AuditEventRecord.event_type)
        .where(AuditEventRecord.run_id == "run-1")
        .order_by(AuditEventRecord.audit_event_id)
    ).all()
    assert event_types == [
        "assessments_json_exported",
        "assessments_csv_exported",
        "review_json_exported",
        "review_csv_exported",
    ]
