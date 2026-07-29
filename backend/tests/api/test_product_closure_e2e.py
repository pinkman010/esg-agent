from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfWriter

from src.config.settings import get_settings
from src.db.models import AssessmentRecord, AssessmentRiskRecord
from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus, RunStatus
from src.domain.models import AnalysisStageEvent, DisclosureAssessment, EvidenceItem
from src.services.analysis_runner import GRI_REQUIREMENTS_PATH, execute_analysis
from src.services.risk_service import calculate_and_store_risk
from src.standards.gri import GRIAdapter


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
            requirements = GRIAdapter(
                GRI_REQUIREMENTS_PATH
            ).load_requirements()
            first_requirement = requirements[0]
            assessment = DisclosureAssessment(
                assessment_id="assessment-e2e",
                run_id=run_id,
                report_id=report_id,
                standard_id="GRI",
                standard_version="2021",
                disclosure_id=first_requirement.disclosure_id,
                requirement_id=first_requirement.requirement_id,
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
                        disclosure_id=requirement.disclosure_id,
                        requirement_id=requirement.requirement_id,
                        verdict="unknown",
                        rationale="未找到有效报告证据。",
                        missing_items=[],
                        model_called=False,
                        review_status="needs_manual_review",
                    )
                    for index, requirement in enumerate(
                        requirements[1:],
                        start=2,
                    )
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
                    for index in range(2, len(requirements) + 1)
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
                eligible_requirement_count=len(requirements),
                succeeded_requirement_count=len(requirements),
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
            "due_date": "2026-08-15",
            "recommendation_text": "在报告主体章节补充法定名称。",
            "created_by": "张三",
        },
    )
    baseline_assessment = Repository(api_session).get_assessment(
        "assessment-e2e"
    )
    baseline_risk = Repository(api_session).latest_risks_for_assessments(
        ["assessment-e2e"]
    )["assessment-e2e"]
    baseline_snapshot = Repository(api_session).latest_review_snapshot(
        "assessment-e2e"
    )
    searched = await api_client.get(
        f"/api/reports/{report_id}/scope-items",
        params={
            "query": "LEGAL NAME",
            "unit_status": "assessed",
            "effective_verdict": "unknown",
            "review_priority": "high",
            "review_status": "reviewed_modified",
        },
    )
    changed_due_date = await api_client.patch(
        f"/api/actions/{action.json()['action_id']}",
        json={"due_date": "2026-09-01"},
    )
    cleared_due_date = await api_client.patch(
        f"/api/actions/{action.json()['action_id']}",
        json={"due_date": None},
    )
    completed_action = await api_client.patch(
        f"/api/actions/{action.json()['action_id']}",
        json={"status": "completed", "completion_note": "已进入下一版报告修改清单"},
    )
    draft = await api_client.post(
        f"/api/reports/{report_id}/exports/draft",
        json={
            "formats": [
                "assessment_xlsx",
                "actions_xlsx",
                "management_pdf",
                "print_html",
            ],
            "created_by": "张三",
        },
    )
    formal = await api_client.post(
        f"/api/reports/{report_id}/exports/formal",
        json={
            "formats": [
                "assessment_xlsx",
                "actions_xlsx",
                "management_pdf",
                "print_html",
            ],
            "created_by": "张三",
        },
    )
    dashboard_after = await api_client.get(f"/api/reports/{report_id}/dashboard")
    downloads = []
    for item in draft.json()["file_manifest"]:
        download = await api_client.get(
            f"/api/exports/{draft.json()['export_id']}"
            f"/files/{item['file_id']}"
        )
        downloads.append((item, download))

    current_repo = Repository(api_session)
    current_assessment = current_repo.get_assessment("assessment-e2e")
    current_risk = current_repo.latest_risks_for_assessments(
        ["assessment-e2e"]
    )["assessment-e2e"]
    current_snapshot = current_repo.latest_review_snapshot(
        "assessment-e2e"
    )

    assert upload.status_code == 200
    assert confirmed.json()["status"] == "ready_for_analysis"
    assert analyzed.json()["status"] == "pending"
    assert run.json()["status"] == "completed"
    assert run.json()["eligible_requirement_count"] == 499
    assert len(stages.json()) == 7
    assert dashboard_before.json()["high_risk_total"] == 1
    assert dashboard_before.json()["high_risk_reviewed"] == 0
    assert queue.json()["total"] == 1
    assert draft.status_code == 200
    assert draft.json()["review_scope"]["draft_label"] is True
    assert len(draft.json()["file_manifest"]) == 4
    assert "path" not in draft.text
    assert "relative_path" not in draft.text
    assert blocked_formal.status_code == 409
    assert reviewed.status_code == 200
    assert searched.status_code == 200
    assert searched.json()["total"] == 1
    assert (
        searched.json()["items"][0]["requirement_id"]
        == "GRI 2-1-a"
    )
    assert changed_due_date.json()["due_date"] == "2026-09-01"
    assert cleared_due_date.json()["due_date"] is None
    assert completed_action.json()["status"] == "completed"
    assert formal.status_code == 200
    assert formal.json()["version_number"] == 1
    assert formal.json()["review_scope"]["high_risk_reviewed"] == 1
    assert dashboard_after.json()["high_risk_reviewed"] == 1
    assert len(downloads) == 4
    for item, download in downloads:
        assert download.status_code == 200
        assert len(download.content) == item["size"]
        assert sha256(download.content).hexdigest() == item["sha256"]
    assert current_assessment.verdict == baseline_assessment.verdict
    assert current_assessment.rationale == baseline_assessment.rationale
    assert current_risk.model_dump(mode="json") == baseline_risk.model_dump(
        mode="json"
    )
    assert current_snapshot.model_dump(
        mode="json"
    ) == baseline_snapshot.model_dump(mode="json")

    reopened = await api_client.post(
        "/api/assessments/assessment-e2e/review-decisions",
        json={
            "operation_type": "reopen",
            "reviewer_name": "王五",
            "reason_code": "post_export_correction",
            "reviewer_note": "正式输出后发现需要重新核实证据。",
            "expected_previous_snapshot_id": reviewed.json()["snapshot_id"],
        },
    )
    report_after_reopen = await api_client.get(f"/api/reports/{report_id}")
    blocked_after_reopen = await api_client.post(
        f"/api/reports/{report_id}/exports/formal",
        json={"formats": ["assessment_xlsx"], "created_by": "王五"},
    )
    corrected = await api_client.post(
        "/api/assessments/assessment-e2e/review-decisions",
        json={
            "operation_type": "modify",
            "reviewer_name": "王五",
            "reason_code": "post_export_correction_completed",
            "reviewer_note": "重新核实后完成纠正。",
            "reviewed_verdict": "partially_disclosed",
            "rationale": "人工重新核实后确认部分披露。",
            "missing_items": ["仍需补充法定名称出处"],
            "expected_previous_snapshot_id": reopened.json()["snapshot_id"],
        },
    )
    second_formal = await api_client.post(
        f"/api/reports/{report_id}/exports/formal",
        json={
            "formats": [
                "assessment_xlsx",
                "actions_xlsx",
                "management_pdf",
                "print_html",
            ],
            "created_by": "王五",
        },
    )
    versions = await api_client.get(f"/api/reports/{report_id}/exports")
    history = await api_client.get(
        "/api/assessments/assessment-e2e/review-history"
    )
    first_formal_downloads = []
    for item in formal.json()["file_manifest"]:
        response = await api_client.get(
            f"/api/exports/{formal.json()['export_id']}"
            f"/files/{item['file_id']}"
        )
        first_formal_downloads.append((item, response))
    second_formal_downloads = []
    for item in second_formal.json()["file_manifest"]:
        response = await api_client.get(
            f"/api/exports/{second_formal.json()['export_id']}"
            f"/files/{item['file_id']}"
        )
        second_formal_downloads.append((item, response))

    assert reopened.status_code == 200
    assert report_after_reopen.json()["status"] == "reopened"
    assert blocked_after_reopen.status_code == 409
    assert blocked_after_reopen.json()["detail"]["code"] == (
        "high_risk_review_incomplete"
    )
    assert corrected.status_code == 200
    assert second_formal.status_code == 200
    assert second_formal.json()["version_number"] == 2
    assert second_formal.json()["supersedes_export_id"] == formal.json()[
        "export_id"
    ]
    formal_versions = {
        item["version_number"]: item
        for item in versions.json()
        if not item["is_draft"]
    }
    assert formal_versions[1]["status"] == "superseded"
    assert formal_versions[2]["status"] == "formal"
    assert len(history.json()) == 3
    first_snapshot = next(
        item
        for item in history.json()
        if item["snapshot_id"] == reviewed.json()["snapshot_id"]
    )
    assert first_snapshot == reviewed.json()
    assert {
        item["operation_type"]
        for item in history.json()
    } == {"modify", "reopen"}
    for item, response in first_formal_downloads + second_formal_downloads:
        assert response.status_code == 200
        assert len(response.content) == item["size"]
        assert sha256(response.content).hexdigest() == item["sha256"]
