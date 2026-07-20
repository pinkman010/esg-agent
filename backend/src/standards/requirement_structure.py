from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


class EvaluationRole(StrEnum):
    INDEPENDENT = "independent"
    CONTEXT_ONLY = "context_only"
    METHOD_PENDING = "method_pending"


class StructureStatus(StrEnum):
    VERIFIED = "verified"
    NORMALIZED = "normalized"
    METHOD_PENDING = "method_pending"


_ROLE_BY_ISSUE = {
    "parent_container_as_leaf": EvaluationRole.CONTEXT_ONLY,
    "missing_parent_context": EvaluationRole.INDEPENDENT,
    "merge_split_error": EvaluationRole.METHOD_PENDING,
}


class RequirementStructureDecision(BaseModel):
    requirement_id: str
    issue_code: str
    parent_requirement_id: str | None = None
    source_note: str
    evaluation_role: EvaluationRole | None = None

    @model_validator(mode="after")
    def validate_issue_role(self) -> RequirementStructureDecision:
        try:
            expected_role = _ROLE_BY_ISSUE[self.issue_code]
        except KeyError as exc:
            raise ValueError(f"unsupported structure issue: {self.issue_code}") from exc
        if self.evaluation_role is not None and self.evaluation_role is not expected_role:
            raise ValueError("evaluation_role conflicts with issue_code")
        if self.issue_code == "missing_parent_context" and not self.parent_requirement_id:
            raise ValueError("missing_parent_context requires parent_requirement_id")
        self.evaluation_role = expected_role
        return self


def canonical_requirement_id(
    raw_requirement_id: str,
    canonical_disclosure_id: str | None = None,
) -> str:
    raw_id = str(raw_requirement_id or "").strip()
    if not raw_id:
        raise ValueError("empty requirement_id")
    if raw_id.startswith("GRI "):
        return raw_id
    parts = raw_id.split(":")
    disclosure_id = str(canonical_disclosure_id or "").strip()
    if raw_id.startswith("current_gap:") and len(parts) >= 3:
        disclosure_id = disclosure_id or parts[2]
        suffix = "-".join(part.strip() for part in parts[3:] if part.strip())
        return f"GRI {disclosure_id}{f'-{suffix}' if suffix else ''}"
    return raw_id


def compile_requirement_structure(
    *,
    items: list[dict[str, Any]],
    decisions: list[RequirementStructureDecision],
) -> list[dict[str, Any]]:
    item_by_id: dict[str, dict[str, Any]] = {}
    canonical_ids: list[str] = []
    for item in items:
        canonical_id = canonical_requirement_id(
            str(item.get("requirement_id") or ""),
            str(item.get("canonical_disclosure_id") or "") or None,
        )
        if canonical_id in item_by_id:
            raise ValueError(f"duplicate requirement_id: {canonical_id}")
        text = _normalized_text(item.get("requirement_text"))
        if not text:
            raise ValueError(f"empty requirement_text: {canonical_id}")
        item_by_id[canonical_id] = item
        canonical_ids.append(canonical_id)

    decision_by_id: dict[str, RequirementStructureDecision] = {}
    for decision in decisions:
        if decision.requirement_id in decision_by_id:
            raise ValueError(f"duplicate structure decision: {decision.requirement_id}")
        if decision.requirement_id not in item_by_id:
            raise ValueError(f"structure decision has no checklist item: {decision.requirement_id}")
        decision_by_id[decision.requirement_id] = decision

    context_cache: dict[str, list[str]] = {}

    def context_chain(requirement_id: str, active: tuple[str, ...] = ()) -> list[str]:
        if requirement_id in context_cache:
            return context_cache[requirement_id]
        if requirement_id in active:
            cycle = " -> ".join((*active, requirement_id))
            raise ValueError(f"parent cycle: {cycle}")
        decision = decision_by_id.get(requirement_id)
        if decision is None or not decision.parent_requirement_id:
            context_cache[requirement_id] = []
            return []
        parent_id = decision.parent_requirement_id
        if parent_id not in item_by_id:
            raise ValueError(f"missing parent requirement: {parent_id}")
        chain = [*context_chain(parent_id, (*active, requirement_id)), parent_id]
        context_cache[requirement_id] = chain
        return chain

    compiled: list[dict[str, Any]] = []
    for canonical_id in canonical_ids:
        item = item_by_id[canonical_id]
        decision = decision_by_id.get(canonical_id)
        source_text = _normalized_text(item.get("requirement_text"))
        context_ids = context_chain(canonical_id)
        context_texts = [
            _normalized_text(item_by_id[parent_id].get("requirement_text"))
            for parent_id in context_ids
        ]
        evaluation_role = (
            decision.evaluation_role if decision else EvaluationRole.INDEPENDENT
        )
        if evaluation_role is EvaluationRole.METHOD_PENDING:
            structure_status = StructureStatus.METHOD_PENDING
        elif decision is None:
            structure_status = StructureStatus.VERIFIED
        else:
            structure_status = StructureStatus.NORMALIZED
        compiled.append(
            {
                **item,
                "source_requirement_text": source_text,
                "effective_requirement_text": _normalized_text(
                    " ".join((*context_texts, source_text))
                ),
                "evaluation_role": evaluation_role.value,
                "structure_status": structure_status.value,
                "context_requirement_ids": context_ids,
                "structure_issue_codes": [decision.issue_code] if decision else [],
            }
        )
    return compiled


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").split())
