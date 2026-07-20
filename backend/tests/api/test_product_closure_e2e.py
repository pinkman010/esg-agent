from io import BytesIO

import pytest
from pypdf import PdfWriter

from src.config.settings import get_settings
from src.db.models import AssessmentRecord, AssessmentRiskRecord
from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus, RunStatus
from src.domain.models import AnalysisStageEvent, DisclosureAssessment, EvidenceItem
from src.services.analysis_runner import execute_analysis
from src.services.risk_service import calculate_and_store_risk


pytestmark = pytest.mark.anyio


def _pdf_bytes() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    return buffer.getvalue()


async def test_product_closure_from_upload_to_formal_export(api_client, api_session, monkeypatch):
    class FakeWorkflow:
        def __init__(self, repository, *args, **kwargs):
            self.repository = repository

        def run(
            self,
            report_id,
            pdf_path,
            source_file_hash,
            confirm_llm,
            enable_ocr=False,
            ocr_pages=None,
            run_id=None,
            requirement_ids=None,
        ):
            assessment = DisclosureAssessment(
                assessment_id="assessment-e2e",
                run_id=run_id,
                report_id=report_id,
                standard_id="GRI",
                standard_version="2021",
                disclosure_id="GRI 2-1",
                requirement_id="GRI 2-1-a",
                verdict=AssessmentVerdict.UNKNOWN,
                rationale="证据质量需要人工确认。",
                missing_items=["可直接核实的组织法定名称"],
                evidence=[
                    EvidenceItem(
                        evidence_id="evidence-e2e",
                        run_id=run_id,
                        report_id=report_id,
                        source_text="测试公司",
                        source_page=1,
                        source_file_hash=source_file_hash,
                        source_method=EvidenceSourceMethod.PDFPLUMBER,
                        needs_ocr_or_vlm=True,
                    )
                ],
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
            )
            self.repository.save_assessment(assessment)
            self.repository.save_evidence_item(
                assessment.assessment_id,
                assessment.evidence[0],
            )
            calculate_and_store_risk(
                self.repository,
                assessment,
                trigger_event="analysis_completed",
                risk_rule_version="risk-v2.1",
            )
            self.repository.session.add_all(
                [
                    AssessmentRecord(
                        assessment_id=f"assessment-e2e-{index:03d}",
                        run_id=run_id,
                        report_id=report_id,
                        standard_id="GRI",
                        standard_version="2021",
                        disclosure_id=f"GRI TEST-{index}",
                        requirement_id=f"GRI TEST-{index}-a",
                        verdict="unknown",
                        rationale="未找到有效报告证据。",
                        missing_items=[],
                        model_called=False,
                        review_status="needs_manual_review",
                    )
                    for index in range(2, 578)
                ]
            )
            self.repository.session.flush()
            self.repository.session.add_all(
                [
                    AssessmentRiskRecord(
                        risk_id=f"risk-e2e-{index:03d}",
                        assessment_id=f"assessment-e2e-{index:03d}",
                        risk_level="low",
                        reason_codes=["unknown_verdict", "no_valid_evidence"],
                        risk_rule_version="risk-v2.1",
                        evidence_status="missing",
                        applicability_status="undetermined",
                        trigger_event="analysis_completed",
                    )
                    for index in range(2, 578)
                ]
            )
            self.repository.session.commit()
            for stage_code in (
                "file_validation",
                "pdf_parsing",
                "report_structure",
                "requirement_matching",
                "evidence_assessment",
                "risk_classification",
                "result_summary",
            ):
                self.repository.append_analysis_stage_event(
                    AnalysisStageEvent(
                        run_id=run_id,
                        stage_code=stage_code,
                        status="completed",
                        completed_units=1,
                        total_units=1,
                    )
                )
            return self.repository.update_run_status(
                run_id,
                RunStatus.COMPLETED,
                eligible_requirement_count=577,
                succeeded_requirement_count=577,
            )

    monkeypatch.setattr("src.services.analysis_runner.SingleReportWorkflow", FakeWorkflow)

    def execute_test_job(
        *,
        report_id,
        run_id,
        confirm_llm,
        enable_ocr=False,
        ocr_pages=None,
        requirement_ids=None,
    ):
        repo = Repository(api_session)
        execute_analysis(
            repo,
            repo.get_report(report_id),
            get_settings(),
            run_id=run_id,
            confirm_llm=confirm_llm,
            enable_ocr=enable_ocr,
            ocr_pages=ocr_pages,
            requirement_ids=requirement_ids,
        )

    monkeypatch.setattr("src.api.routes.reports.execute_analysis_job", execute_test_job)

    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("测试公司 ESG 报告 2024.pdf", _pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]
    confirmed = await api_client.post(
        f"/api/reports/{report_id}/confirm-metadata",
        json={"company_name": "测试公司", "report_year": 2024, "language": "zh-CN"},
    )
    analyzed = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False, "enable_ocr": False},
    )
    run_id = analyzed.json()["run_id"]

    run = await api_client.get(f"/api/runs/{run_id}")
    stages = await api_client.get(f"/api/runs/{run_id}/stages")
    dashboard_before = await api_client.get(f"/api/reports/{report_id}/dashboard")
    queue = await api_client.get(f"/api/reports/{report_id}/review-queue")
    draft = await api_client.post(
        f"/api/reports/{report_id}/exports/draft",
        json={"formats": ["assessment_xlsx", "management_pdf", "print_html"], "created_by": "张三"},
    )
    blocked_formal = await api_client.post(
        f"/api/reports/{report_id}/exports/formal",
        json={"formats": ["assessment_xlsx"], "created_by": "张三"},
    )
    reviewed = await api_client.post(
        "/api/assessments/assessment-e2e/review-decisions",
        json={
            "operation_type": "modify",
            "reviewer_name": "张三",
            "reason_code": "manual_evidence_confirmed",
            "reviewer_note": "人工确认当前仍缺证据",
            "reviewed_verdict": "unknown",
            "rationale": "人工确认未披露组织法定名称。",
            "missing_items": ["组织法定名称"],
        },
    )
    action = await api_client.post(
        f"/api/reports/{report_id}/actions",
        json={
            "assessment_id": "assessment-e2e",
            "title": "补充组织法定名称",
            "priority": "high",
            "owner_name": "李四",
            "recommendation_text": "在报告主体章节补充法定名称。",
            "created_by": "张三",
        },
    )
    completed_action = await api_client.patch(
        f"/api/actions/{action.json()['action_id']}",
        json={"status": "completed", "completion_note": "已进入下一版报告修改清单"},
    )
    formal = await api_client.post(
        f"/api/reports/{report_id}/exports/formal",
        json={"formats": ["assessment_xlsx", "management_pdf", "print_html"], "created_by": "张三"},
    )
    dashboard_after = await api_client.get(f"/api/reports/{report_id}/dashboard")

    assert upload.status_code == 200
    assert confirmed.json()["status"] == "ready_for_analysis"
    assert analyzed.json()["status"] == "pending"
    assert run.json()["status"] == "completed"
    assert run.json()["eligible_requirement_count"] == 577
    assert len(stages.json()) == 7
    assert dashboard_before.json()["high_risk_total"] == 1
    assert dashboard_before.json()["high_risk_reviewed"] == 0
    assert queue.json()["total"] == 1
    assert draft.status_code == 200
    assert draft.json()["review_scope"]["draft_label"] is True
    assert blocked_formal.status_code == 409
    assert reviewed.status_code == 200
    assert completed_action.json()["status"] == "completed"
    assert formal.status_code == 200
    assert formal.json()["version_number"] == 1
    assert formal.json()["review_scope"]["high_risk_reviewed"] == 1
    assert dashboard_after.json()["high_risk_reviewed"] == 1
