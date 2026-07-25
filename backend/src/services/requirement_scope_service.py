from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from src.domain.enums import RiskLevel
from src.standards.gri import GRIAdapter
from src.standards.requirement_structure import canonical_requirement_id


class RequirementScopeService:
    def __init__(self, repository: Any, adapter: GRIAdapter):
        self.repository = repository
        self.adapter = adapter

    def scope_summary(self) -> dict[str, int]:
        self.adapter.load_scope_items()
        return self.adapter.get_scope_summary()

    def list_items(self, report_id: str) -> list[dict[str, Any]]:
        raw_items = self.adapter.load_scope_items()
        summary = self.adapter.get_scope_summary()
        canonical_items = [
            (
                canonical_requirement_id(
                    str(item.get("requirement_id") or ""),
                    str(item.get("canonical_disclosure_id") or "") or None,
                ),
                item,
            )
            for item in raw_items
        ]
        independent_ids = {
            requirement_id
            for requirement_id, item in canonical_items
            if item.get("evaluation_role") == "independent"
        }
        expected_independent = summary["independent_assessment_count"]
        if len(independent_ids) != expected_independent:
            raise ValueError(
                "GRI scope manifest does not contain the declared independent "
                f"assessment count: expected {expected_independent}, "
                f"got {len(independent_ids)}"
            )

        run = self.repository.latest_run_for_report(report_id)
        assessments_by_requirement: dict[str, Any] = {}
        risks: dict[str, Any] = {}
        snapshots: dict[str, Any] = {}
        if run is not None:
            assessments = self.repository.list_assessments_by_run(run.run_id)
            assessments_by_requirement = {
                assessment.requirement_id: assessment for assessment in assessments
            }
            if (
                len(assessments_by_requirement) != expected_independent
                or set(assessments_by_requirement) != independent_ids
            ):
                raise ValueError(
                    "analysis run must contain exactly "
                    f"{expected_independent} independent assessments for the "
                    "frozen 577-unit scope"
                )
            assessment_ids = [
                assessment.assessment_id
                for assessment in assessments_by_requirement.values()
            ]
            risks = self.repository.latest_risks_for_assessments(assessment_ids)
            snapshots = self.repository.latest_snapshots_for_assessments(
                assessment_ids
            )

        incorporated_into: dict[str, list[str]] = defaultdict(list)
        for requirement_id, item in canonical_items:
            if item.get("evaluation_role") != "independent":
                continue
            for context_id in item.get("context_requirement_ids") or []:
                incorporated_into[str(context_id)].append(requirement_id)

        scope_items = [
            self._scope_item(
                requirement_id=requirement_id,
                item=item,
                assessment=assessments_by_requirement.get(requirement_id),
                risks=risks,
                snapshots=snapshots,
                incorporated_into=incorporated_into,
            )
            for requirement_id, item in canonical_items
        ]
        scope_items.sort(
            key=lambda item: _requirement_sort_key(item["requirement_id"])
        )
        if len(scope_items) != summary["standard_unit_count"]:
            raise ValueError(
                "GRI scope service did not preserve all declared standard units"
            )
        return scope_items

    def _scope_item(
        self,
        *,
        requirement_id: str,
        item: dict[str, Any],
        assessment: Any | None,
        risks: dict[str, Any],
        snapshots: dict[str, Any],
        incorporated_into: dict[str, list[str]],
    ) -> dict[str, Any]:
        is_context = item.get("evaluation_role") == "context_only"
        if is_context:
            return {
                "requirement_id": requirement_id,
                "gri_topic": _topic(requirement_id),
                "unit_status": "context_incorporated",
                "source_requirement_text": str(
                    item.get("source_requirement_text")
                    or item.get("requirement_text")
                    or ""
                ),
                "effective_requirement_text": str(
                    item.get("effective_requirement_text")
                    or item.get("requirement_text")
                    or ""
                ),
                "component_requirement_ids": list(
                    item.get("component_requirement_ids") or []
                ),
                "incorporated_into_requirement_ids": sorted(
                    incorporated_into.get(requirement_id, []),
                    key=_requirement_sort_key,
                ),
                "assessment_id": None,
                "effective_verdict": None,
                "review_priority": None,
                "review_status": None,
                "source_pdf_pages": [],
            }

        risk = risks.get(assessment.assessment_id) if assessment is not None else None
        snapshot = (
            snapshots.get(assessment.assessment_id)
            if assessment is not None
            else None
        )
        source_pages = (
            sorted(
                {
                    evidence.source_pdf_page or evidence.source_page
                    for evidence in assessment.evidence
                }
            )
            if assessment is not None
            else []
        )
        effective_verdict = None
        if assessment is not None:
            effective_verdict = (
                snapshot.reviewed_verdict.value
                if snapshot is not None and snapshot.reviewed_verdict is not None
                else assessment.verdict.value
            )
        return {
            "requirement_id": requirement_id,
            "gri_topic": _topic(requirement_id),
            "unit_status": "assessed",
            "source_requirement_text": str(
                item.get("source_requirement_text")
                or item.get("requirement_text")
                or ""
            ),
            "effective_requirement_text": str(
                item.get("effective_requirement_text")
                or item.get("requirement_text")
                or ""
            ),
            "component_requirement_ids": list(
                item.get("component_requirement_ids") or []
            ),
            "incorporated_into_requirement_ids": [],
            "assessment_id": (
                assessment.assessment_id if assessment is not None else None
            ),
            "effective_verdict": effective_verdict,
            "review_priority": (
                risk.risk_level.value
                if risk is not None
                else RiskLevel.HIGH.value
                if assessment is not None
                else None
            ),
            "review_status": (
                _review_status(snapshot) if assessment is not None else None
            ),
            "source_pdf_pages": source_pages,
        }


def _topic(requirement_id: str) -> str:
    parts = requirement_id.split("-")
    return parts[0] if len(parts) < 2 else "-".join(parts[:2])


def _review_status(snapshot: Any | None) -> str:
    if snapshot is None:
        return "pending_review"
    return {
        "approve": "reviewed_approved",
        "modify": "reviewed_modified",
        "invalidate_evidence": "evidence_invalidated",
        "reopen": "reopened",
        "legacy_import": "reviewed_approved",
    }.get(snapshot.operation_type.value, "pending_review")


def _requirement_sort_key(requirement_id: str) -> tuple[Any, ...]:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", requirement_id)
        if part
    )
