import pytest

pytestmark = pytest.mark.anyio


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
