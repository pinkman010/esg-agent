import pytest

pytestmark = pytest.mark.anyio

from sqlalchemy import select

from src.db.models import AuditEventRecord
from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReportStatus, ReviewOperation, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, EvidenceItem, Report, ReviewDecision
from src.services.risk_service import calculate_and_store_risk
from src.services.review_service import ReviewService


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
        evidence=[
            EvidenceItem(
                evidence_id="evidence-1",
                run_id="run-1",
                report_id="report-1",
                source_text="独立有限鉴证报告",
                source_page=77,
                source_pdf_page=77,
                source_report_page=76,
                source_file_hash="hash-1",
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                quality_flags=[PageQualityFlag.SHORT_TEXT, PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED],
                needs_ocr_or_vlm=True,
                requires_ocr=True,
                requires_vlm=False,
                ocr_or_vlm_reason="assurance_page_text_too_short",
                metadata={
                    "candidate_pdf_pages": [77],
                    "candidate_report_pages": [76],
                },
            )
        ],
        review_status=ReviewStatus.NOT_REQUIRED,
    )
    repo.save_assessment(assessment)
    repo.save_evidence_item("assessment-1", assessment.evidence[0])
    calculate_and_store_risk(repo, assessment, trigger_event="analysis_completed")
    repo.save_review_decision(ReviewDecision(decision_id="decision-1", run_id="run-1", assessment_id="assessment-1", review_status=ReviewStatus.APPROVED, reviewer_note="Checked."))


async def test_export_api_returns_json_and_csv(api_client, api_session):
    seed_export_data(api_session)

    assessments_json = await api_client.get("/api/exports/runs/run-1/assessments.json")
    assessments_csv = await api_client.get("/api/exports/runs/run-1/assessments.csv")
    review_json = await api_client.get("/api/exports/runs/run-1/review.json")
    review_csv = await api_client.get("/api/exports/runs/run-1/review.csv")

    assert assessments_json.status_code == 200
    assert assessments_json.json()[0]["assessment_id"] == "assessment-1"
    assert assessments_json.json()[0]["source_pdf_page"] == 77
    assert assessments_json.json()[0]["source_report_page"] == 76
    assert assessments_json.json()[0]["page_label"] == "PDF 第 77 页 / 报告页 76"
    assert assessments_json.json()[0]["needs_ocr_or_vlm"] is True
    assert assessments_json.json()[0]["requires_ocr"] is True
    assert assessments_json.json()[0]["requires_vlm"] is False
    assert assessments_json.json()[0]["evidence_preview"] == "独立有限鉴证报告"
    assert assessments_json.json()[0]["candidate_pdf_pages"] == [77]
    assert assessments_json.json()[0]["candidate_report_pages"] == [76]
    assert assessments_csv.status_code == 200
    assert "assessment_id" in assessments_csv.text
    assert "source_pdf_page" in assessments_csv.text
    assert "source_report_page" in assessments_csv.text
    assert "page_label" in assessments_csv.text
    assert "PDF 第 77 页 / 报告页 76" in assessments_csv.text
    assert "needs_ocr_or_vlm" in assessments_csv.text
    assert "requires_ocr" in assessments_csv.text
    assert "requires_vlm" in assessments_csv.text
    assert "evidence_preview" in assessments_csv.text
    assert "candidate_pdf_pages" in assessments_csv.text
    assert "candidate_report_pages" in assessments_csv.text
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


async def test_versioned_draft_and_formal_exports(api_client, api_session):
    seed_export_data(api_session)

    draft = await api_client.post(
        "/api/reports/report-1/exports/draft",
        json={"formats": ["assessment_xlsx", "management_pdf", "print_html"], "created_by": "张三"},
    )
    blocked = await api_client.post(
        "/api/reports/report-1/exports/formal",
        json={"formats": ["assessment_xlsx"], "created_by": "张三"},
    )
    ReviewService(Repository(api_session)).record(
        "assessment-1",
        operation_type=ReviewOperation.APPROVE,
        reviewer_name="张三",
        reason_code="system_result_confirmed",
    )
    formal = await api_client.post(
        "/api/reports/report-1/exports/formal",
        json={"formats": ["assessment_xlsx"], "created_by": "张三"},
    )
    second_formal = await api_client.post(
        "/api/reports/report-1/exports/formal",
        json={"formats": ["assessment_xlsx"], "created_by": "张三"},
    )
    listed = await api_client.get("/api/reports/report-1/exports")

    assert draft.status_code == 200
    assert draft.json()["is_draft"] is True
    assert draft.json()["review_scope"]["draft_label"] is True
    assert len(draft.json()["file_manifest"]) == 3
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == {"code": "high_risk_review_incomplete", "remaining": 1}
    assert formal.status_code == 200
    assert formal.json()["version_number"] == 1
    assert formal.json()["is_draft"] is False
    assert second_formal.status_code == 200
    assert second_formal.json()["version_number"] == 2
    assert second_formal.json()["supersedes_export_id"] == formal.json()["export_id"]
    assert len(listed.json()) == 3
    first_formal = next(item for item in listed.json() if item["export_id"] == formal.json()["export_id"])
    assert first_formal["status"] == "superseded"
    assert Repository(api_session).get_report("report-1").status is ReportStatus.FORMALLY_EXPORTED
