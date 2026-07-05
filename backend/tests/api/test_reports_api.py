import pytest
from pypdf import PdfWriter

from src.api.routes.reports import GRI_REQUIREMENT_PACK_PATH, GRI_REQUIREMENTS_LIMIT, GRI_REQUIREMENTS_PATH

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


async def test_upload_rejects_non_pdf(api_client):
    response = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.txt", b"not pdf", "text/plain")},
    )

    assert response.status_code == 400


async def test_analyze_creates_run_without_model_call(api_client):
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]

    response = await api_client.post(f"/api/reports/{report_id}/analyze", json={"confirm_llm": False})

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert body["report_id"] == report_id
    assert body["status"] in {"completed", "failed"}
    assert body["confirm_llm"] is False


async def test_analyze_defaults_to_ocr_disabled(api_client, monkeypatch):
    captured = {}

    class FakeWorkflow:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, report_id, pdf_path, source_file_hash, confirm_llm, enable_ocr=False, ocr_pages=None):
            captured["enable_ocr"] = enable_ocr
            captured["ocr_pages"] = ocr_pages
            from src.domain.enums import RunStatus
            from src.domain.models import AnalysisRun

            return AnalysisRun(run_id="run-1", report_id=report_id, status=RunStatus.COMPLETED, confirm_llm=confirm_llm)

    monkeypatch.setattr("src.api.routes.reports.SingleReportWorkflow", FakeWorkflow)
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]

    response = await api_client.post(f"/api/reports/{report_id}/analyze", json={"confirm_llm": False})

    assert response.status_code == 200
    assert captured == {"enable_ocr": False, "ocr_pages": []}


async def test_analyze_passes_explicit_ocr_pages(api_client, monkeypatch):
    captured = {}

    class FakeWorkflow:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, report_id, pdf_path, source_file_hash, confirm_llm, enable_ocr=False, ocr_pages=None):
            captured["enable_ocr"] = enable_ocr
            captured["ocr_pages"] = ocr_pages
            from src.domain.enums import RunStatus
            from src.domain.models import AnalysisRun

            return AnalysisRun(run_id="run-1", report_id=report_id, status=RunStatus.COMPLETED, confirm_llm=confirm_llm)

    monkeypatch.setattr("src.api.routes.reports.SingleReportWorkflow", FakeWorkflow)
    upload = await api_client.post(
        "/api/reports/upload",
        files={"file": ("report.pdf", make_pdf_bytes(), "application/pdf")},
    )
    report_id = upload.json()["report_id"]

    response = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False, "enable_ocr": True, "ocr_pages": [77]},
    )

    assert response.status_code == 200
    assert captured == {"enable_ocr": True, "ocr_pages": [77]}


async def test_reports_api_uses_real_gri_checklist_path():
    assert GRI_REQUIREMENTS_PATH.as_posix().endswith("backend/data/manifests/gri_requirement_checklist.json")
    assert GRI_REQUIREMENTS_LIMIT == 10
    assert GRI_REQUIREMENTS_PATH.exists()
    assert GRI_REQUIREMENT_PACK_PATH.as_posix().endswith("backend/data/manifests/gri_requirement_pack.json")
    assert GRI_REQUIREMENT_PACK_PATH.exists()
