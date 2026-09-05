from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


EXPECTED_COUNTS = {
    "standard_unit_count": 577,
    "eligible_requirement_count": 499,
    "context_only_count": 78,
    "method_pending_count": 0,
}
REQUIRED_AUDIT_EVENTS = {
    "report_uploaded",
    "report_metadata_confirmed",
    "report_profile_resolved",
    "analysis_completed",
    "review_snapshot_created",
    "improvement_action_created",
    "improvement_action_updated",
    "draft_export_created",
    "export_file_downloaded",
}
DEFAULT_DRAFT_FORMATS = (
    "assessment_xlsx",
    "actions_xlsx",
    "management_pdf",
    "print_html",
)


class DeliveryFlowError(RuntimeError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _request(client: httpx.Client, method: str, path: str, *, stage: str, **kwargs) -> httpx.Response:
    try:
        response = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise DeliveryFlowError(
            "HTTP_REQUEST_FAILED", f"{stage} request could not be completed"
        ) from exc
    if not response.is_success:
        raise DeliveryFlowError(
            "HTTP_REQUEST_FAILED", f"{stage} returned HTTP {response.status_code}"
        )
    return response


def _json(response: httpx.Response, *, stage: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise DeliveryFlowError(
            "HTTP_RESPONSE_INVALID", f"{stage} did not return JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise DeliveryFlowError(
            "HTTP_RESPONSE_INVALID", f"{stage} returned an unexpected JSON shape"
        )
    return payload


def _required_string(payload: dict[str, Any], field: str, *, stage: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise DeliveryFlowError(
            "HTTP_RESPONSE_INVALID", f"{stage} omitted {field}"
        )
    return value


def _wait_for_completed_run(
    client: httpx.Client,
    run_id: str,
    *,
    poll_interval_seconds: float,
    poll_timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + poll_timeout_seconds
    while True:
        run = _json(
            _request(client, "GET", f"/api/runs/{run_id}", stage="analysis poll"),
            stage="analysis poll",
        )
        status = run.get("status")
        if status == "completed":
            return run
        if status in {"failed", "partially_completed"}:
            raise DeliveryFlowError(
                "ANALYSIS_NOT_COMPLETED", f"analysis ended with status {status}"
            )
        if time.monotonic() >= deadline:
            raise DeliveryFlowError(
                "ANALYSIS_TIMEOUT", "analysis did not complete within the configured timeout"
            )
        if poll_interval_seconds:
            time.sleep(poll_interval_seconds)


def _verify_run_contract(run: dict[str, Any]) -> int:
    if run.get("confirm_llm") is not False:
        raise DeliveryFlowError(
            "EXTERNAL_FEATURE_ENABLED", "analysis did not preserve confirm_llm=false"
        )
    mismatches = {
        field: run.get(field)
        for field, expected in EXPECTED_COUNTS.items()
        if run.get(field) != expected
    }
    if mismatches:
        raise DeliveryFlowError(
            "SCOPE_COUNT_MISMATCH", f"unexpected count fields: {sorted(mismatches)}"
        )
    ai_summary = run.get("ai_summary")
    if not isinstance(ai_summary, dict):
        raise DeliveryFlowError("HTTP_RESPONSE_INVALID", "run omitted ai_summary")
    suggestion_count = sum(
        int(ai_summary.get(field) or 0)
        for field in ("succeeded", "failed", "skipped")
    )
    if suggestion_count != 0:
        raise DeliveryFlowError(
            "AI_SUGGESTION_PRESENT", "demo analysis created an AI suggestion"
        )
    return suggestion_count


def _load_all_audit_events(client: httpx.Client, report_id: str) -> tuple[int, list[dict[str, Any]]]:
    offset = 0
    events: list[dict[str, Any]] = []
    total = 0
    while True:
        payload = _json(
            _request(
                client,
                "GET",
                f"/api/reports/{report_id}/audit",
                stage="audit",
                params={"offset": offset, "limit": 100},
            ),
            stage="audit",
        )
        items = payload.get("items")
        if not isinstance(items, list) or not isinstance(payload.get("total"), int):
            raise DeliveryFlowError("HTTP_RESPONSE_INVALID", "audit response is incomplete")
        total = payload["total"]
        events.extend(item for item in items if isinstance(item, dict))
        offset += len(items)
        if offset >= total:
            return total, events
        if not items:
            raise DeliveryFlowError("HTTP_RESPONSE_INVALID", "audit pagination made no progress")


def verify_delivery_flow(
    *,
    api_base: str,
    report_path: Path,
    output_path: Path,
    transport: httpx.BaseTransport | None = None,
    poll_interval_seconds: float = 1.0,
    poll_timeout_seconds: float = 600.0,
    draft_formats: tuple[str, ...] = DEFAULT_DRAFT_FORMATS,
) -> dict[str, Any]:
    report_path = Path(report_path)
    output_path = Path(output_path)
    if not report_path.is_file() or report_path.suffix.casefold() != ".pdf":
        raise DeliveryFlowError("DEMO_REPORT_MISSING", "a generated demo PDF is required")
    parsed_base = urlparse(api_base)
    if transport is None and (
        parsed_base.scheme != "http" or parsed_base.hostname not in {"localhost", "127.0.0.1"}
    ):
        raise DeliveryFlowError(
            "API_BASE_REJECTED", "real delivery verification is limited to local HTTP"
        )
    if poll_interval_seconds < 0 or poll_timeout_seconds <= 0:
        raise DeliveryFlowError("INVALID_TIMEOUT", "poll timing must be positive")
    if not draft_formats:
        raise DeliveryFlowError("DRAFT_FORMATS_EMPTY", "at least one draft format is required")

    report_content = report_path.read_bytes()
    with httpx.Client(base_url=api_base.rstrip("/"), transport=transport, timeout=120.0) as client:
        upload = _json(
            _request(
                client,
                "POST",
                "/api/reports/upload",
                stage="upload",
                params={"duplicate_policy": "create_new"},
                files={"file": (report_path.name, report_content, "application/pdf")},
            ),
            stage="upload",
        )
        report_id = _required_string(upload, "report_id", stage="upload")
        server_file_hash = _required_string(upload, "file_hash", stage="upload")

        _request(
            client,
            "POST",
            f"/api/reports/{report_id}/confirm-metadata",
            stage="metadata confirmation",
            json={
                "company_name": "ESG-Agent Demo Manufacturing Co., Ltd.",
                "report_year": 2025,
                "language": "en",
            },
        )
        analyze = _json(
            _request(
                client,
                "POST",
                f"/api/reports/{report_id}/analyze",
                stage="analysis start",
                json={"confirm_llm": False, "enable_ocr": False},
            ),
            stage="analysis start",
        )
        run_id = _required_string(analyze, "run_id", stage="analysis start")
        run = _wait_for_completed_run(
            client,
            run_id,
            poll_interval_seconds=poll_interval_seconds,
            poll_timeout_seconds=poll_timeout_seconds,
        )
        suggestion_count = _verify_run_contract(run)

        scope = _json(
            _request(
                client,
                "GET",
                f"/api/reports/{report_id}/scope-items",
                stage="scope",
                params={"page": 1, "page_size": 1},
            ),
            stage="scope",
        )
        if scope.get("total") != 577:
            raise DeliveryFlowError("SCOPE_COUNT_MISMATCH", "scope total is not 577")

        assessments = _json(
            _request(
                client,
                "GET",
                f"/api/reports/{report_id}/assessments",
                stage="assessments",
                params={"page": 1, "page_size": 1},
            ),
            stage="assessments",
        )
        items = assessments.get("items")
        if assessments.get("total") != 499 or not isinstance(items, list) or not items:
            raise DeliveryFlowError(
                "ASSESSMENT_COUNT_MISMATCH", "assessment total is not 499"
            )
        assessment_id = _required_string(items[0], "assessment_id", stage="assessments")
        detail = _json(
            _request(
                client,
                "GET",
                f"/api/reports/{report_id}/assessments/{assessment_id}",
                stage="assessment detail",
            ),
            stage="assessment detail",
        )
        if detail.get("latest_ai_suggestion") is not None:
            raise DeliveryFlowError(
                "AI_SUGGESTION_PRESENT", "assessment contains an AI suggestion"
            )
        system_verdict = _required_string(
            detail, "system_verdict", stage="assessment detail"
        )
        rationale = str(detail.get("system_rationale") or "Synthetic engineering verification.")
        missing_items = detail.get("system_missing_items")
        if not isinstance(missing_items, list):
            missing_items = []

        snapshot = _json(
            _request(
                client,
                "POST",
                f"/api/assessments/{assessment_id}/review-decisions",
                stage="manual review",
                json={
                    "operation_type": "modify",
                    "reviewer_name": "Delivery verifier",
                    "reason_code": "synthetic_delivery_verification",
                    "reviewer_note": "Engineering workflow verification only; no professional ESG conclusion.",
                    "reviewed_verdict": system_verdict,
                    "rationale": rationale,
                    "missing_items": missing_items,
                },
            ),
            stage="manual review",
        )
        snapshot_id = _required_string(snapshot, "snapshot_id", stage="manual review")

        action = _json(
            _request(
                client,
                "POST",
                f"/api/reports/{report_id}/actions",
                stage="action creation",
                json={
                    "assessment_id": assessment_id,
                    "title": "Synthetic delivery verification action",
                    "priority": "medium",
                    "owner_name": "Delivery verifier",
                    "due_date": "2027-12-31",
                    "recommendation_text": "Verify the local remediation workflow.",
                    "created_by": "Delivery verifier",
                },
            ),
            stage="action creation",
        )
        action_id = _required_string(action, "action_id", stage="action creation")
        updated_action = _json(
            _request(
                client,
                "PATCH",
                f"/api/actions/{action_id}",
                stage="action update",
                json={"owner_name": "Delivery verifier", "due_date": "2027-11-30"},
            ),
            stage="action update",
        )
        if updated_action.get("owner_name") != "Delivery verifier":
            raise DeliveryFlowError("ACTION_UPDATE_MISMATCH", "action update was not retained")

        draft = _json(
            _request(
                client,
                "POST",
                f"/api/reports/{report_id}/exports/draft",
                stage="draft export",
                json={"formats": list(draft_formats), "created_by": "Delivery verifier"},
            ),
            stage="draft export",
        )
        if draft.get("is_draft") is not True:
            raise DeliveryFlowError("DRAFT_EXPORT_INVALID", "export was not marked as draft")
        export_id = _required_string(draft, "export_id", stage="draft export")
        file_manifest = draft.get("file_manifest")
        if not isinstance(file_manifest, list) or len(file_manifest) != len(draft_formats):
            raise DeliveryFlowError(
                "DRAFT_EXPORT_INVALID", "draft file count does not match requested formats"
            )
        verified_files = []
        for item in file_manifest:
            if not isinstance(item, dict):
                raise DeliveryFlowError("DRAFT_EXPORT_INVALID", "draft file entry is invalid")
            file_id = _required_string(item, "file_id", stage="draft export")
            downloaded = _request(
                client,
                "GET",
                f"/api/exports/{export_id}/files/{file_id}",
                stage="draft download",
            ).content
            actual_hash = _sha256_bytes(downloaded)
            if len(downloaded) != item.get("size") or actual_hash != item.get("sha256"):
                raise DeliveryFlowError(
                    "DOWNLOAD_CHECKSUM_MISMATCH", f"draft file {file_id} failed integrity check"
                )
            verified_files.append(
                {
                    "file_id": file_id,
                    "format": item.get("format"),
                    "size": len(downloaded),
                    "sha256": actual_hash,
                }
            )

        audit_total, audit_events = _load_all_audit_events(client, report_id)
        event_types = {
            item.get("event_type")
            for item in audit_events
            if isinstance(item.get("event_type"), str)
        }
        missing_events = sorted(REQUIRED_AUDIT_EVENTS - event_types)
        if missing_events:
            raise DeliveryFlowError(
                "AUDIT_EVENTS_MISSING", f"required event types missing: {missing_events}"
            )

    result = {
        "schema_version": 1,
        "status": "passed",
        "report": {
            "report_id": report_id,
            "source_sha256": _sha256_bytes(report_content),
            "server_file_hash": server_file_hash,
        },
        "run": {"run_id": run_id, **EXPECTED_COUNTS},
        "scope_total": scope["total"],
        "assessment_total": assessments["total"],
        "review": {"assessment_id": assessment_id, "snapshot_id": snapshot_id},
        "action": {"action_id": action_id, "updated": True},
        "draft": {
            "export_id": export_id,
            "artifact_count": len(verified_files),
            "files": verified_files,
        },
        "audit": {
            "total": audit_total,
            "required_event_types": sorted(REQUIRED_AUDIT_EVENTS),
        },
        "external_features": {
            "confirm_llm": False,
            "enable_ocr": False,
            "ai_suggestion_count": suggestion_count,
        },
        "formal_export_created": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the local ESG-Agent demo flow")
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--poll-timeout", type=float, default=600.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args(argv)
    try:
        result = verify_delivery_flow(
            api_base=args.api_base,
            report_path=args.report,
            output_path=args.output,
            poll_timeout_seconds=args.poll_timeout,
            poll_interval_seconds=args.poll_interval,
        )
    except DeliveryFlowError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "DELIVERY_FLOW_PASSED "
        f"report_id={result['report']['report_id']} run_id={result['run']['run_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
