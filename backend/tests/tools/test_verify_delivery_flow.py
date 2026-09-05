from __future__ import annotations

import hashlib
import importlib.util
import json

import httpx
import pytest


MODULE_NAME = "src.tools.verify_delivery_flow"


def test_delivery_flow_verifier_module_exists():
    assert importlib.util.find_spec(MODULE_NAME) is not None


def _response(request: httpx.Request, status_code: int, payload=None, content: bytes | None = None):
    if content is not None:
        return httpx.Response(status_code, content=content, request=request)
    return httpx.Response(status_code, json=payload, request=request)


def test_delivery_flow_uses_safe_fixed_sequence_and_writes_evidence(tmp_path):
    from src.tools.verify_delivery_flow import verify_delivery_flow

    report = tmp_path / "demo.pdf"
    report.write_bytes(b"%PDF-1.4 synthetic")
    output = tmp_path / "delivery-flow.json"
    download = b"draft-artifact"
    download_hash = hashlib.sha256(download).hexdigest()
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == "/api/reports/upload":
            assert request.url.params["duplicate_policy"] == "create_new"
            return _response(request, 200, {"report_id": "report-demo", "file_hash": "source-hash"})
        if path == "/api/reports/report-demo/confirm-metadata":
            assert json.loads(request.content) == {
                "company_name": "ESG-Agent Demo Manufacturing Co., Ltd.",
                "report_year": 2025,
                "language": "en",
            }
            return _response(request, 200, {"report_id": "report-demo"})
        if path == "/api/reports/report-demo/analyze":
            assert json.loads(request.content) == {"confirm_llm": False, "enable_ocr": False}
            return _response(request, 200, {"run_id": "run-demo", "status": "pending"})
        if path == "/api/runs/run-demo":
            return _response(
                request,
                200,
                {
                    "status": "completed",
                    "confirm_llm": False,
                    "standard_unit_count": 577,
                    "eligible_requirement_count": 499,
                    "context_only_count": 78,
                    "method_pending_count": 0,
                    "ai_summary": {"eligible": 0, "succeeded": 0, "failed": 0, "skipped": 0},
                },
            )
        if path == "/api/reports/report-demo/scope-items":
            return _response(request, 200, {"items": [], "page": 1, "page_size": 1, "total": 577})
        if path == "/api/reports/report-demo/assessments":
            return _response(
                request,
                200,
                {
                    "items": [{"assessment_id": "assessment-demo", "system_verdict": "not_disclosed"}],
                    "page": 1,
                    "page_size": 1,
                    "total": 499,
                },
            )
        if path == "/api/reports/report-demo/assessments/assessment-demo":
            return _response(
                request,
                200,
                {
                    "assessment_id": "assessment-demo",
                    "system_verdict": "not_disclosed",
                    "system_rationale": "Synthetic engineering verification.",
                    "system_missing_items": ["report evidence"],
                    "latest_ai_suggestion": None,
                },
            )
        if path == "/api/assessments/assessment-demo/review-decisions":
            body = json.loads(request.content)
            assert body["operation_type"] == "modify"
            assert body["reviewed_verdict"] == "not_disclosed"
            return _response(request, 200, {"snapshot_id": "snapshot-demo"})
        if path == "/api/reports/report-demo/actions":
            return _response(request, 200, {"action_id": "action-demo"})
        if path == "/api/actions/action-demo":
            return _response(request, 200, {"action_id": "action-demo", "owner_name": "Delivery verifier"})
        if path == "/api/reports/report-demo/exports/draft":
            return _response(
                request,
                200,
                {
                    "export_id": "export-demo",
                    "is_draft": True,
                    "file_manifest": [
                        {
                            "file_id": "file-demo",
                            "format": "print_html",
                            "filename": "demo.html",
                            "size": len(download),
                            "sha256": download_hash,
                        }
                    ],
                },
            )
        if path == "/api/exports/export-demo/files/file-demo":
            return _response(request, 200, content=download)
        if path == "/api/reports/report-demo/audit":
            events = [
                "report_uploaded",
                "report_metadata_confirmed",
                "report_profile_resolved",
                "analysis_completed",
                "review_snapshot_created",
                "improvement_action_created",
                "improvement_action_updated",
                "draft_export_created",
                "export_file_downloaded",
            ]
            return _response(
                request,
                200,
                {
                    "items": [{"event_type": event, "payload": {}} for event in events],
                    "total": len(events),
                    "offset": 0,
                    "limit": 100,
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    result = verify_delivery_flow(
        api_base="http://delivery.invalid",
        report_path=report,
        output_path=output,
        transport=httpx.MockTransport(handler),
        poll_interval_seconds=0,
        poll_timeout_seconds=5,
        draft_formats=("print_html",),
    )

    assert result["status"] == "passed"
    assert result["external_features"] == {
        "confirm_llm": False,
        "enable_ocr": False,
        "ai_suggestion_count": 0,
    }
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8")) == result
    assert calls == [
        ("POST", "/api/reports/upload"),
        ("POST", "/api/reports/report-demo/confirm-metadata"),
        ("POST", "/api/reports/report-demo/analyze"),
        ("GET", "/api/runs/run-demo"),
        ("GET", "/api/reports/report-demo/scope-items"),
        ("GET", "/api/reports/report-demo/assessments"),
        ("GET", "/api/reports/report-demo/assessments/assessment-demo"),
        ("POST", "/api/assessments/assessment-demo/review-decisions"),
        ("POST", "/api/reports/report-demo/actions"),
        ("PATCH", "/api/actions/action-demo"),
        ("POST", "/api/reports/report-demo/exports/draft"),
        ("GET", "/api/exports/export-demo/files/file-demo"),
        ("GET", "/api/reports/report-demo/audit"),
    ]


@pytest.mark.parametrize(
    ("status_code", "run_payload", "expected_code"),
    [
        (503, None, "HTTP_REQUEST_FAILED"),
        (
            200,
            {
                "status": "completed",
                "confirm_llm": False,
                "standard_unit_count": 576,
                "eligible_requirement_count": 499,
                "context_only_count": 78,
                "method_pending_count": 0,
                "ai_summary": {"eligible": 0, "succeeded": 0, "failed": 0, "skipped": 0},
            },
            "SCOPE_COUNT_MISMATCH",
        ),
    ],
)
def test_delivery_flow_returns_stable_error_codes(tmp_path, status_code, run_payload, expected_code):
    from src.tools.verify_delivery_flow import DeliveryFlowError, verify_delivery_flow

    report = tmp_path / "demo.pdf"
    report.write_bytes(b"%PDF-1.4 synthetic")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/reports/upload":
            return _response(request, status_code, run_payload or {"detail": "unavailable"})
        raise AssertionError(f"unexpected request after failed upload: {request.url}")

    if expected_code == "SCOPE_COUNT_MISMATCH":
        responses = iter(
            [
                {"report_id": "report-demo", "file_hash": "source-hash"},
                {"report_id": "report-demo"},
                {"run_id": "run-demo", "status": "pending"},
                run_payload,
            ]
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return _response(request, 200, next(responses))

    with pytest.raises(DeliveryFlowError) as raised:
        verify_delivery_flow(
            api_base="http://delivery.invalid",
            report_path=report,
            output_path=tmp_path / "result.json",
            transport=httpx.MockTransport(handler),
            poll_interval_seconds=0,
            poll_timeout_seconds=5,
        )
    assert raised.value.code == expected_code
