import pytest
from pypdf import PdfWriter
from sqlalchemy import select

from src.db.models import AuditEventRecord
from src.db.repositories import Repository
from src.domain.enums import ReportStatus, RunStatus
from src.domain.models import AnalysisRun, Report
from src.services.analysis_runner import GRI_REQUIREMENT_PACK_PATH, GRI_REQUIREMENTS_LIMIT, GRI_REQUIREMENTS_PATH
from src.services.metadata_detection import DetectedReportMetadata

pytestmark = pytest.mark.anyio


def make_pdf_bytes():
    from io import BytesIO

    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    return buffer.getvalue()


async def test_upload_accepts_pdf_and_returns_report_id(api_client):
    response = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["report_id"]
    assert body["original_filename"] == "report.pdf"
    assert body["file_hash"]
    assert body["status"] == "uploaded"


async def test_report_file_is_embedded_inline_instead_of_downloaded(api_client):
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )

    response = await api_client.get(f"/api/reports/{upload.json()['report_id']}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    disposition = response.headers.get("content-disposition", "")
    assert disposition.startswith("inline")
    assert "attachment" not in disposition


async def test_upload_persists_detected_metadata_candidates(api_client, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.reports.detect_report_metadata",
        lambda *_: DetectedReportMetadata(
            page_count=78,
            metadata={
                "original_filename": "Envision Energy 2024-zh.pdf",
                "company_name": "远景能源有限公司",
                "report_year": 2024,
                "language": "zh-CN",
            },
        ),
    )

    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("Envision Energy 2024-zh.pdf", make_pdf_bytes(), "application/pdf")},
    )
    detail = await api_client.get(f"/api/reports/{upload.json()['report_id']}")

    assert detail.status_code == 200
    assert detail.json()["company_name"] is None
    assert detail.json()["metadata_detected"]["company_name"] == "远景能源有限公司"
    assert detail.json()["metadata_detected"]["report_year"] == 2024
    assert detail.json()["metadata_detected"]["language"] == "zh-CN"


async def test_upload_rejects_duplicate_file_hash_with_existing_report_id(api_client):
    payload = make_pdf_bytes()
    first = await api_client.post(
        "/api/reports/upload",
        files={"file": ("first.pdf", payload, "application/pdf")},
    )

    duplicate = await api_client.post(
        "/api/reports/upload",
        files={"file": ("duplicate.pdf", payload, "application/pdf")},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_report"
    assert duplicate.json()["detail"]["report_id"] == first.json()["report_id"]
    assert duplicate.json()["detail"]["existing_report_status"] == "uploaded"
    assert duplicate.json()["detail"]["can_start_new_demo"] is False


async def test_upload_explicit_create_new_preserves_existing_report(api_client, api_session):
    payload = make_pdf_bytes()
    first = await api_client.post(
        "/api/reports/upload",
        files={"file": ("first.pdf", payload, "application/pdf")},
    )

    second = await api_client.post(
        "/api/reports/upload",
        params={"duplicate_policy": "create_new"},
        files={"file": ("second.pdf", payload, "application/pdf")},
    )
    latest_duplicate = await api_client.post(
        "/api/reports/upload",
        files={"file": ("latest-duplicate.pdf", payload, "application/pdf")},
    )

    assert second.status_code == 200
    assert second.json()["report_id"] != first.json()["report_id"]
    assert second.json()["file_hash"] == first.json()["file_hash"]
    assert latest_duplicate.status_code == 409
    assert latest_duplicate.json()["detail"]["report_id"] == second.json()["report_id"]

    reports = await api_client.get("/api/reports", params={"page": 1, "page_size": 10})
    assert reports.status_code == 200
    assert reports.json()["total"] == 2
    assert {item["report_id"] for item in reports.json()["items"]} == {
        first.json()["report_id"],
        second.json()["report_id"],
    }

    upload_events = api_session.scalars(
        select(AuditEventRecord)
        .where(AuditEventRecord.event_type == "report_uploaded")
        .order_by(AuditEventRecord.audit_event_id)
    ).all()
    assert upload_events[-1].event_payload["duplicate_of_report_id"] == first.json()["report_id"]


async def test_reports_list_is_paginated_and_detail_exposes_metadata(api_client):
    first = await api_client.post(
        "/api/reports/upload",
        files={"file": ("Alpha ESG Report 2024.pdf", make_pdf_bytes(), "application/pdf")},
    )
    await api_client.post(
        "/api/reports/upload",
        files={"file": ("Beta ESG Report 2023.pdf", make_pdf_bytes() + b" ", "application/pdf")},
    )

    response = await api_client.get("/api/reports", params={"page": 1, "page_size": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) == 1

    detail = await api_client.get(f"/api/reports/{first.json()['report_id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "uploaded"
    assert detail.json()["metadata_detected"]["report_year"] == 2024
    assert detail.json()["page_count"] == 1


async def test_confirm_metadata_makes_report_ready_for_analysis(api_client):
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )

    response = await api_client.post(
        f"/api/reports/{upload.json()['report_id']}/confirm-metadata",
        json={"company_name": "测试公司", "report_year": 2024, "language": "zh-CN"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "测试公司"
    assert body["report_year"] == 2024
    assert body["language"] == "zh-CN"
    assert body["status"] == "ready_for_analysis"
    assert body["metadata_confirmed_at"] is not None

    corrected = await api_client.post(
        f"/api/reports/{upload.json()['report_id']}/confirm-metadata",
        json={"company_name": "更正后的公司", "report_year": 2023, "language": "zh-CN"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["status"] == "ready_for_analysis"
    assert corrected.json()["company_name"] == "更正后的公司"
    assert corrected.json()["report_year"] == 2023


@pytest.mark.parametrize(
    "status",
    [
        ReportStatus.ANALYZING,
        ReportStatus.ANALYSIS_COMPLETED,
        ReportStatus.PARTIALLY_COMPLETED,
        ReportStatus.ANALYSIS_FAILED,
    ],
)
async def test_confirm_metadata_rejects_reports_that_entered_analysis(
    api_client,
    api_session,
    status,
):
    report_id = f"report-metadata-locked-{status.value}"
    Repository(api_session).create_report(
        Report(
            report_id=report_id,
            original_filename="report.pdf",
            stored_path="x",
            file_hash=f"hash-{status.value}",
            status=status,
        )
    )

    response = await api_client.post(
        f"/api/reports/{report_id}/confirm-metadata",
        json={"company_name": "测试公司", "report_year": 2024, "language": "zh-CN"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "report_metadata_locked",
        "message": "报告已进入分析流程",
    }


async def test_upload_rejects_non_pdf(api_client):
    response = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.txt", b"not pdf", "text/plain")},
    )

    assert response.status_code == 400


async def test_analyze_creates_run_without_model_call(api_client, monkeypatch):
    class FakeWorkflow:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, report_id, pdf_path, source_file_hash, confirm_llm, enable_ocr=False, ocr_pages=None, run_id=None, requirement_ids=None):
            from src.domain.enums import RunStatus
            from src.domain.models import AnalysisRun

            return AnalysisRun(run_id=run_id, report_id=report_id, status=RunStatus.COMPLETED, confirm_llm=confirm_llm)

    monkeypatch.setattr("src.services.analysis_runner.SingleReportWorkflow", FakeWorkflow)
    monkeypatch.setattr("src.api.routes.reports.execute_analysis_job", lambda **kwargs: None)
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]
    await api_client.post(
        f"/api/reports/{report_id}/confirm-metadata",
        json={"company_name": "测试公司", "report_year": 2024, "language": "zh-CN"},
    )

    response = await api_client.post(f"/api/reports/{report_id}/analyze", json={"confirm_llm": False})

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert body["report_id"] == report_id
    assert body["status"] == "pending"
    assert body["confirm_llm"] is False


async def test_analyze_rejects_unconfirmed_report(api_client):
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )

    response = await api_client.post(
        f"/api/reports/{upload.json()['report_id']}/analyze",
        json={"confirm_llm": False},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "report_not_ready"


@pytest.mark.parametrize(
    ("run_status", "report_status"),
    [
        (RunStatus.PENDING, ReportStatus.READY_FOR_ANALYSIS),
        (RunStatus.RUNNING, ReportStatus.ANALYZING),
    ],
)
async def test_analyze_rejects_existing_active_run(
    api_client,
    api_session,
    run_status,
    report_status,
):
    report_id = f"report-active-{run_status.value}"
    repo = Repository(api_session)
    repo.create_report(
        Report(
            report_id=report_id,
            original_filename="report.pdf",
            stored_path="x",
            file_hash=f"hash-active-{run_status.value}",
            status=report_status,
        )
    )
    repo.create_run(
        AnalysisRun(
            run_id="run-active",
            report_id=report_id,
            status=run_status,
        )
    )

    response = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "analysis_already_running",
        "run_id": "run-active",
    }


async def test_analyze_defaults_to_ocr_disabled(api_client, monkeypatch):
    captured = {}

    class FakeWorkflow:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, report_id, pdf_path, source_file_hash, confirm_llm, enable_ocr=False, ocr_pages=None, run_id=None, requirement_ids=None):
            captured["enable_ocr"] = enable_ocr
            captured["ocr_pages"] = ocr_pages
            from src.domain.enums import RunStatus
            from src.domain.models import AnalysisRun

            return AnalysisRun(run_id=run_id, report_id=report_id, status=RunStatus.COMPLETED, confirm_llm=confirm_llm)

    monkeypatch.setattr("src.services.analysis_runner.SingleReportWorkflow", FakeWorkflow)
    monkeypatch.setattr(
        "src.api.routes.reports.execute_analysis_job",
        lambda **kwargs: captured.update(
            enable_ocr=kwargs["enable_ocr"],
            ocr_pages=kwargs["ocr_pages"],
        ),
    )
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]
    await api_client.post(
        f"/api/reports/{report_id}/confirm-metadata",
        json={"company_name": "测试公司", "report_year": 2024, "language": "zh-CN"},
    )

    response = await api_client.post(f"/api/reports/{report_id}/analyze", json={"confirm_llm": False})

    assert response.status_code == 200
    assert captured == {"enable_ocr": False, "ocr_pages": []}


async def test_analyze_passes_explicit_ocr_pages(api_client, monkeypatch):
    captured = {}

    class FakeWorkflow:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, report_id, pdf_path, source_file_hash, confirm_llm, enable_ocr=False, ocr_pages=None, run_id=None, requirement_ids=None):
            captured["enable_ocr"] = enable_ocr
            captured["ocr_pages"] = ocr_pages
            from src.domain.enums import RunStatus
            from src.domain.models import AnalysisRun

            return AnalysisRun(run_id=run_id, report_id=report_id, status=RunStatus.COMPLETED, confirm_llm=confirm_llm)

    monkeypatch.setattr("src.services.analysis_runner.SingleReportWorkflow", FakeWorkflow)
    monkeypatch.setattr(
        "src.api.routes.reports.execute_analysis_job",
        lambda **kwargs: captured.update(
            enable_ocr=kwargs["enable_ocr"],
            ocr_pages=kwargs["ocr_pages"],
        ),
    )
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]
    await api_client.post(
        f"/api/reports/{report_id}/confirm-metadata",
        json={"company_name": "测试公司", "report_year": 2024, "language": "zh-CN"},
    )

    response = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False, "enable_ocr": True, "ocr_pages": [77]},
    )

    assert response.status_code == 200
    assert captured == {"enable_ocr": True, "ocr_pages": [77]}


async def test_analyze_queues_background_job_with_identifiers_only(api_client, monkeypatch):
    captured = {}

    def capture_job(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr("src.api.routes.reports.execute_analysis_job", capture_job)
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]
    await api_client.post(
        f"/api/reports/{report_id}/confirm-metadata",
        json={"company_name": "测试公司", "report_year": 2024, "language": "zh-CN"},
    )

    response = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False, "enable_ocr": True, "ocr_pages": [7]},
    )

    assert response.status_code == 200
    assert captured["args"] == ()
    assert captured["kwargs"] == {
        "report_id": report_id,
        "run_id": response.json()["run_id"],
        "confirm_llm": False,
        "enable_ocr": True,
        "ocr_pages": [7],
    }


async def test_analyze_creates_new_run_with_risk_v2_1(
    api_client,
    api_session,
    monkeypatch,
):
    repo = Repository(api_session)
    repo.create_report(
        Report(
            report_id="report-risk-v2-1",
            original_filename="report.pdf",
            stored_path="x",
            file_hash="hash-risk-v2-1",
            status=ReportStatus.READY_FOR_ANALYSIS,
        )
    )
    monkeypatch.setattr(
        "src.api.routes.reports.execute_analysis_job",
        lambda **kwargs: None,
    )

    response = await api_client.post(
        "/api/reports/report-risk-v2-1/analyze",
        json={"confirm_llm": False},
    )

    assert response.status_code == 200
    run = repo.get_run(response.json()["run_id"])
    assert run.risk_rule_version == "risk-v2.1"


async def test_reports_api_uses_real_gri_checklist_path():
    assert GRI_REQUIREMENTS_PATH.as_posix().endswith(
        "backend/data/manifests/gri_requirement_checklist_v2.json"
    )
    assert GRI_REQUIREMENTS_LIMIT is None
    assert GRI_REQUIREMENTS_PATH.exists()
    assert GRI_REQUIREMENT_PACK_PATH.as_posix().endswith("backend/data/manifests/gri_requirement_pack.json")
    assert GRI_REQUIREMENT_PACK_PATH.exists()
