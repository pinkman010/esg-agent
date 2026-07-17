import pytest

from src.api.routes import demo as demo_route
from src.services.demo_environment import (
    DemoActiveRunsError,
    DemoResetResult,
    DemoRuntimeCleanupError,
)


pytestmark = pytest.mark.anyio


async def test_demo_reset_is_hidden_in_non_demo_environment(api_client):
    response = await api_client.post(
        "/api/demo/reset",
        json={"confirmation": "RESET_DEMO"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "demo_reset_unavailable"


async def test_demo_reset_returns_cleared_counts(api_client, monkeypatch):
    monkeypatch.setattr(
        demo_route,
        "reset_demo_environment_data",
        lambda *args, **kwargs: DemoResetResult(
            cleared_report_count=3,
            cleared_runtime_directories=("uploads", "derived"),
        ),
    )

    response = await api_client.post(
        "/api/demo/reset",
        json={"confirmation": "RESET_DEMO"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "cleared_report_count": 3,
        "cleared_runtime_directories": ["uploads", "derived"],
    }


async def test_demo_reset_rejects_active_run(api_client, monkeypatch):
    def fail(*args, **kwargs):
        raise DemoActiveRunsError("run-active")

    monkeypatch.setattr(demo_route, "reset_demo_environment_data", fail)

    response = await api_client.post(
        "/api/demo/reset",
        json={"confirmation": "RESET_DEMO"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "demo_reset_blocked_active_run",
        "run_id": "run-active",
    }


async def test_demo_reset_reports_runtime_cleanup_failure(api_client, monkeypatch):
    def fail(*args, **kwargs):
        raise DemoRuntimeCleanupError(cleared_report_count=2)

    monkeypatch.setattr(demo_route, "reset_demo_environment_data", fail)

    response = await api_client.post(
        "/api/demo/reset",
        json={"confirmation": "RESET_DEMO"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "code": "demo_runtime_cleanup_failed",
        "cleared_report_count": 2,
    }


async def test_demo_reset_requires_exact_confirmation(api_client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        demo_route,
        "reset_demo_environment_data",
        lambda *args, **kwargs: calls.append(kwargs),
    )

    response = await api_client.post(
        "/api/demo/reset",
        json={"confirmation": "reset_demo"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "demo_reset_confirmation_invalid"
    assert calls == []
