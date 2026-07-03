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

