import csv
import json
from dataclasses import dataclass
from functools import cache
from importlib import resources


@dataclass(frozen=True)
class CompilationGuardrail:
    compilation_requirement_id: str
    target_requirement_ids: tuple[str, ...]
    facets: tuple[str, ...]
    missing_item_templates: tuple[str, ...]
    guardrail_effects: tuple[str, ...]


@cache
def load_compilation_guardrails() -> tuple[CompilationGuardrail, ...]:
    data_path = resources.files("src.standards.data").joinpath("compilation_requirement_guardrails.csv")
    with data_path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(_guardrail_from_row(row) for row in csv.DictReader(handle))


@cache
def compilation_guardrails_by_target() -> dict[str, tuple[CompilationGuardrail, ...]]:
    grouped: dict[str, list[CompilationGuardrail]] = {}
    for guardrail in load_compilation_guardrails():
        for target_id in guardrail.target_requirement_ids:
            grouped.setdefault(target_id, []).append(guardrail)
    return {target_id: tuple(items) for target_id, items in grouped.items()}


def get_compilation_guardrails(requirement_id: str) -> tuple[CompilationGuardrail, ...]:
    return compilation_guardrails_by_target().get(requirement_id, ())


def _guardrail_from_row(row: dict[str, str]) -> CompilationGuardrail:
    return CompilationGuardrail(
        compilation_requirement_id=row["compilation_requirement_id"],
        target_requirement_ids=tuple(_parse_json_list(row.get("target_requirement_ids", "[]"))),
        facets=tuple(_parse_json_list(row.get("facet", "[]"))),
        missing_item_templates=tuple(_parse_json_list(row.get("missing_item_template", "[]"))),
        guardrail_effects=tuple(_parse_json_list(row.get("guardrail_effect", "[]"))),
    )


def _parse_json_list(value: str) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON list, got {type(parsed).__name__}")
    return [str(item) for item in parsed]
