import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.anyio
async def test_health_returns_ok_status():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}