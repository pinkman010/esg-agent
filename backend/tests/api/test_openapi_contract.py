import json
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio


async def test_openapi_exposes_v1_3_release_version(api_client):
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    project_root = Path(__file__).parents[3]
    backend_version = tomllib.loads(
        (project_root / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    frontend_version = json.loads(
        (project_root / "frontend" / "package.json").read_text(encoding="utf-8")
    )["version"]

    assert {
        response.json()["info"]["version"],
        backend_version,
        frontend_version,
    } == {"1.3.0"}


async def test_openapi_exposes_response_schemas_for_frontend_generation(api_client):
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    for schema_name in [
        "AnalysisRun",
        "DisclosureAssessment",
        "Recommendation",
        "ReportUploadResponse",
        "AnalyzeResponse",
        "AuditRun",
    ]:
        assert schema_name in schemas


async def test_openapi_exposes_phase_1_6_product_closure_contract(api_client):
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    contract = response.json()
    assert (
        "/api/exports/{export_id}/files/{file_id}"
        in contract["paths"]
    )
    schemas = contract["components"]["schemas"]
    assert "ExportFileResponse" in schemas
    assert set(schemas["ExportFileResponse"]["properties"]) == {
        "file_id",
        "filename",
        "format",
        "size",
        "sha256",
    }
    scope_parameters = {
        parameter["name"]
        for parameter in contract["paths"][
            "/api/reports/{report_id}/scope-items"
        ]["get"]["parameters"]
    }
    assert {
        "query",
        "unit_status",
        "effective_verdict",
        "review_priority",
        "review_status",
        "applicability_status",
    }.issubset(scope_parameters)
    due_date = schemas["UpdateActionRequest"]["properties"]["due_date"]
    assert {"type": "string", "format": "date"} in due_date["anyOf"]
    formats = schemas["GenerateExportRequest"]["properties"]["formats"]
    assert "actions_xlsx" in formats["items"]["enum"]


async def test_openapi_exposes_phase_1_7_scope_and_report_audit_contract(
    api_client,
):
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    contract = response.json()
    schemas = contract["components"]["schemas"]
    assert {
        "ReportAuditEventResponse",
        "ReportAuditListResponse",
    } <= set(schemas)
    assert (
        "/api/reports/{report_id}/audit"
        in contract["paths"]
    )
    audit_parameters = {
        parameter["name"]
        for parameter in contract["paths"][
            "/api/reports/{report_id}/audit"
        ]["get"]["parameters"]
    }
    assert audit_parameters == {
        "report_id",
        "event_type",
        "offset",
        "limit",
    }
    scope_item = schemas["RequirementScopeItemResponse"]
    assert {
        "analysis_status",
        "source_run_id",
        "failure_code",
        "failure_message",
    } <= set(scope_item["properties"])
    assert "analysis_status" not in scope_item.get("required", [])
    assert "source_run_id" not in scope_item.get("required", [])


async def test_openapi_keeps_phase_1_7_compatibility_fields_and_constraints(
    api_client,
):
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    analysis_run = schemas["AnalysisRun"]
    assert {
        "run_id",
        "report_id",
        "status",
        "confirm_llm",
        "failure_summary",
    } <= set(analysis_run["properties"])
    assert set(analysis_run["required"]) == {
        "run_id",
        "report_id",
    }
    assert analysis_run["properties"]["status"]["default"] == "pending"
    assert analysis_run["properties"]["confirm_llm"]["default"] is False
    retry_reason = schemas["RetryFailedRequest"]["properties"]["reason"]
    assert retry_reason["minLength"] == 1
    assert retry_reason["maxLength"] == 500
