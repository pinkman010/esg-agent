from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import select

from src.config.settings import get_settings
from src.db.models import EvidenceItemRecord
from src.db.repositories import Repository
from src.services.analysis_runner import execute_analysis


pytestmark = pytest.mark.anyio

GOLDWIND_PDF = Path("data/reports/Goldwind 2024-zh.pdf")


async def test_goldwind_digital_pdf_product_closure(
    api_client,
    api_session,
    monkeypatch,
):
    source_bytes = GOLDWIND_PDF.read_bytes()
    source_hash = sha256(source_bytes).hexdigest()

    def execute_test_job(
        *,
        report_id,
        run_id,
        confirm_llm,
        enable_ocr=False,
        ocr_pages=None,
        requirement_ids=None,
    ):
        repository = Repository(api_session)
        execute_analysis(
            repository,
            repository.get_report(report_id),
            get_settings(),
            run_id=run_id,
            confirm_llm=confirm_llm,
            enable_ocr=enable_ocr,
            ocr_pages=ocr_pages,
            requirement_ids=requirement_ids,
        )

    monkeypatch.setattr(
        "src.api.routes.reports.execute_analysis_job",
        execute_test_job,
    )

    upload = await api_client.post(
        "/api/reports/upload",
        files={
            "file": (
                "Goldwind 2024-zh.pdf",
                source_bytes,
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 200
    report_id = upload.json()["report_id"]
    assert upload.json()["file_hash"] == source_hash
    uploaded_report = await api_client.get(f"/api/reports/{report_id}")
    assert uploaded_report.json()["page_count"] == 52

    confirmed = await api_client.post(
        f"/api/reports/{report_id}/confirm-metadata",
        json={
            "company_name": "Goldwind",
            "report_year": 2024,
            "language": "en",
        },
    )
    assert confirmed.status_code == 200

    analyzed = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False, "enable_ocr": False},
    )
    assert analyzed.status_code == 200
    run_id = analyzed.json()["run_id"]

    run = await api_client.get(f"/api/runs/{run_id}")
    scope = await api_client.get(
        f"/api/reports/{report_id}/scope-items",
        params={"limit": 600},
    )
    assert run.json()["status"] == "completed"
    assert run.json()["confirm_llm"] is False
    assert run.json()["standard_unit_count"] == 577
    assert run.json()["eligible_requirement_count"] == 499
    assert run.json()["context_only_count"] == 78
    assert run.json()["method_pending_count"] == 0
    assert scope.status_code == 200
    assert scope.json()["total"] == 577

    repository = Repository(api_session)
    assessments = repository.list_assessments_by_run(run_id)
    assert len(assessments) == 499
    assert repository.list_ai_suggestions_for_run(run_id) == []
    evidence_records = api_session.scalars(
        select(EvidenceItemRecord).where(
            EvidenceItemRecord.run_id == run_id
        )
    ).all()
    assert all(
        1 <= (item.source_pdf_page or item.source_page) <= 52
        for item in evidence_records
    )
    assert all(
        item.evidence_metadata.get("retrieval_strategy")
        != "global_fallback"
        for item in evidence_records
    )

    assessment = assessments[0]
    reviewed = await api_client.post(
        f"/api/assessments/{assessment.assessment_id}/review-decisions",
        json={
            "operation_type": "modify",
            "reviewer_name": "工程验收",
            "reason_code": "phase17_engineering_acceptance",
            "reviewer_note": "仅验证产品闭环，不构成 ESG 专业判断。",
            "reviewed_verdict": assessment.verdict.value,
            "rationale": "工程验收人工快照，不构成 ESG 专业结论。",
            "missing_items": assessment.missing_items,
        },
    )
    assert reviewed.status_code == 200

    action = await api_client.post(
        f"/api/reports/{report_id}/actions",
        json={
            "assessment_id": assessment.assessment_id,
            "title": "Goldwind 工程验收整改项",
            "priority": "medium",
            "owner_name": "验收负责人",
            "due_date": "2026-08-15",
            "recommendation_text": "验证整改任务产品流程。",
            "created_by": "工程验收",
        },
    )
    assert action.status_code == 200
    updated_action = await api_client.patch(
        f"/api/actions/{action.json()['action_id']}",
        json={
            "owner_name": "更新负责人",
            "due_date": "2026-09-01",
        },
    )
    assert updated_action.status_code == 200
    assert updated_action.json()["owner_name"] == "更新负责人"
    assert updated_action.json()["due_date"] == "2026-09-01"

    draft = await api_client.post(
        f"/api/reports/{report_id}/exports/draft",
        json={
            "formats": [
                "assessment_xlsx",
                "actions_xlsx",
                "management_pdf",
                "print_html",
            ],
            "created_by": "工程验收",
        },
    )
    assert draft.status_code == 200
    assert len(draft.json()["file_manifest"]) == 4

    expected_media_types = {
        "assessment_xlsx": (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        "actions_xlsx": (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        "management_pdf": "application/pdf",
        "print_html": "text/html; charset=utf-8",
    }
    for item in draft.json()["file_manifest"]:
        download = await api_client.get(
            f"/api/exports/{draft.json()['export_id']}"
            f"/files/{item['file_id']}"
        )
        assert download.status_code == 200
        assert download.headers["content-type"] == expected_media_types[
            item["format"]
        ]
        assert item["filename"] in download.headers["content-disposition"]
        assert download.content
        assert len(download.content) == item["size"]
        assert sha256(download.content).hexdigest() == item["sha256"]

    audit = await api_client.get(
        f"/api/reports/{report_id}/audit",
        params={"limit": 100},
    )
    assert audit.status_code == 200
    event_types = {
        item["event_type"]
        for item in audit.json()["items"]
    }
    assert {
        "report_uploaded",
        "report_metadata_confirmed",
        "report_profile_resolved",
        "analysis_completed",
        "review_snapshot_created",
        "improvement_action_created",
        "improvement_action_updated",
        "draft_export_created",
        "export_file_downloaded",
    } <= event_types
    profile_event = next(
        item
        for item in audit.json()["items"]
        if item["event_type"] == "report_profile_resolved"
    )
    assert profile_event["payload"]["profile_id"] == "goldwind_2024"
