import pytest

from src.services.ocr_capability import OcrCapability


pytestmark = pytest.mark.anyio


async def test_ocr_capability_is_non_blocking_and_safe(api_client, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.capabilities.inspect_ocr_capability",
        lambda settings: OcrCapability(
            enabled=True,
            available=False,
            dependency_codes=("ghostscript_missing",),
            language="chi_sim+eng",
            max_pages=5,
        ),
    )

    response = await api_client.get("/api/capabilities/ocr")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "available": False,
        "dependency_codes": ["ghostscript_missing"],
        "language": "chi_sim+eng",
        "max_pages": 5,
    }
    assert ":\\" not in response.text


async def test_core_health_remains_ok_when_ocr_is_unavailable(api_client, monkeypatch):
    def fail_if_called(_settings):
        raise AssertionError("health must not inspect OCR capability")

    monkeypatch.setattr(
        "src.api.routes.capabilities.inspect_ocr_capability",
        fail_if_called,
    )

    response = await api_client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_openapi_registers_ocr_capability_without_changing_health_schema(api_client):
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/capabilities/ocr" in schema["paths"]
    assert schema["paths"]["/api/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {
        "additionalProperties": {"type": "string"},
        "type": "object",
        "title": "Response Health Api Health Get",
    }
