from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from src.standards.compilation_guardrails import get_compilation_guardrails
from src.standards.evidence_contracts import get_requirement_contract
from src.standards.evidence_ontology import EvidenceKind


DEFAULT_SEED_REQUIREMENT_IDS = {
    "GRI 205-1-a",
    "GRI 205-1-b",
    "GRI 414-1-a",
    "GRI 403-9-a-i",
    "GRI 418-1-a",
}

SELECTION_COLUMNS = [
    "requirement_id",
    "selection_bucket",
    "selection_theme",
    "semantic_group",
    "evidence_kinds",
    "route_status",
    "candidate_page_source",
    "selection_reason",
]

TARGETED_THEMES = {
    "ohs_kpi": {"403"},
    "supplier_environment_social_assessment": {"308", "414"},
    "energy_ghg_kpi": {"302", "305"},
    "employee_turnover_parental_leave": {"401", "402", "404", "405"},
    "zero_event_compliance": {"406", "416", "417", "418"},
}

TARGETED_THEME_QUOTAS = {
    "ohs_kpi": 12,
    "supplier_environment_social_assessment": 4,
    "energy_ghg_kpi": 12,
    "employee_turnover_parental_leave": 11,
    "zero_event_compliance": 11,
}


def select_stratified_requirements(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    requirements = _aggregate_requirements(rows)
    disclosed = [item for item in requirements if item["verdict"] == "disclosed"]
    if len(disclosed) > 15:
        raise ValueError(f"disclosed requirements exceed 15: {len(disclosed)}")

    selected: list[dict[str, str]] = []
    selected_ids: set[str] = set()
    _append_selection(selected, selected_ids, disclosed, "all_disclosed", len(disclosed))

    non_disclosed = [item for item in requirements if item["verdict"] != "disclosed"]
    boundary_count = 10 + (15 - len(disclosed))
    boundary = sorted(non_disclosed, key=_boundary_sort_key)
    _append_selection(selected, selected_ids, boundary, "boundary_guardrail", boundary_count)

    partial = [item for item in requirements if item["verdict"] == "partially_disclosed"]
    _append_selection(selected, selected_ids, partial, "partial_stratified", 35, preserve_seeds=True)

    unknown = [item for item in requirements if item["verdict"] == "unknown"]
    _append_selection(selected, selected_ids, unknown, "unknown_stratified", 40, preserve_seeds=True)

    if len(selected) != 100:
        raise ValueError(f"unable to select exactly 100 requirements: {len(selected)}")
    missing_seeds = DEFAULT_SEED_REQUIREMENT_IDS - selected_ids
    if missing_seeds:
        raise ValueError(f"seed requirements missing from sample: {sorted(missing_seeds)}")
    return sorted(selected, key=lambda item: (_bucket_order(item["selection_bucket"]), _natural_key(item["requirement_id"])))


def select_targeted_requirements(
    rows: list[dict[str, str]],
    excluded_requirement_ids: set[str],
) -> list[dict[str, str]]:
    requirements = _aggregate_requirements(rows)
    selected: list[dict[str, str]] = []
    selected_ids = set(excluded_requirement_ids)
    for theme, topics in TARGETED_THEMES.items():
        quota = TARGETED_THEME_QUOTAS[theme]
        pool = [
            item
            for item in requirements
            if str(item["requirement_id"]) not in selected_ids
            and _requirement_topic(str(item["requirement_id"])) in topics
        ]
        chosen = _round_robin_by_route(pool, quota)
        if len(chosen) < quota:
            raise ValueError(f"insufficient requirements for {theme}: expected {quota}, got {len(chosen)}")
        for item in chosen:
            requirement_id = str(item["requirement_id"])
            selected_ids.add(requirement_id)
            selected.append(
                {
                    "requirement_id": requirement_id,
                    "selection_bucket": "targeted_50",
                    "selection_theme": theme,
                    "semantic_group": str(item["semantic_group"]),
                    "evidence_kinds": json.dumps(item["evidence_kinds"], ensure_ascii=False),
                    "route_status": str(item["route_status"]),
                    "candidate_page_source": str(item["candidate_page_source"]),
                    "selection_reason": f"targeted:{theme}:{item['route_status']}",
                }
            )
    return selected


def write_selection(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SELECTION_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)


def write_summary(rows: list[dict[str, str]], output_path: Path) -> None:
    bucket_counts: dict[str, int] = defaultdict(int)
    semantic_group_counts: dict[str, int] = defaultdict(int)
    route_status_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        bucket_counts[row["selection_bucket"]] += 1
        semantic_group_counts[row["semantic_group"]] += 1
        route_status_counts[row["route_status"]] += 1
    payload = {
        "selected_requirement_count": len(rows),
        "unique_requirement_count": len({row["requirement_id"] for row in rows}),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "semantic_group_counts": dict(sorted(semantic_group_counts.items())),
        "route_status_counts": dict(sorted(route_status_counts.items())),
        "seed_requirement_ids": sorted(DEFAULT_SEED_REQUIREMENT_IDS, key=_natural_key),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)


def _aggregate_requirements(rows: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        requirement_id = (row.get("requirement_id") or "").strip()
        if requirement_id:
            grouped[requirement_id].append(row)

    output: list[dict[str, object]] = []
    valid_evidence_kinds = {kind.value for kind in EvidenceKind}
    for requirement_id, requirement_rows in grouped.items():
        contract = get_requirement_contract(requirement_id)
        semantic_group = contract.semantic_group.value if contract and contract.semantic_group else "unclassified"
        if contract:
            evidence_kinds = sorted({kind.value for kind in contract.evidence_kinds})
        else:
            evidence_kinds = sorted(
                {
                    value
                    for row in requirement_rows
                    for value in [(row.get("evidence_kind") or "").strip(), (row.get("evidence_type") or "").strip()]
                    if value in valid_evidence_kinds
                }
            )
        candidate_pages = {
            page
            for row in requirement_rows
            for page in _parse_pages(row.get("candidate_pdf_pages", ""))
        }
        source_pages = {
            page
            for row in requirement_rows
            for page in _parse_pages(row.get("source_pdf_page", ""))
        }
        candidate_sources = sorted(
            {(row.get("candidate_page_source") or "").strip() for row in requirement_rows}
            - {""}
        )
        route_status = "no_candidate"
        if candidate_pages and source_pages:
            route_status = "candidate_with_evidence"
        elif candidate_pages:
            route_status = "candidate_without_evidence"
        output.append(
            {
                "requirement_id": requirement_id,
                "verdict": _first_non_empty(requirement_rows, "verdict"),
                "semantic_group": semantic_group,
                "evidence_kinds": evidence_kinds,
                "route_status": route_status,
                "candidate_page_source": "+".join(candidate_sources),
                "candidate_pages": candidate_pages,
                "source_pages": source_pages,
                "has_complex_table": any("complex_table" in (row.get("quality_flags") or "") for row in requirement_rows),
                "has_guardrail": bool(get_compilation_guardrails(requirement_id)),
            }
        )
    return sorted(output, key=lambda item: _natural_key(str(item["requirement_id"])))


def _append_selection(
    output: list[dict[str, str]],
    selected_ids: set[str],
    pool: list[dict[str, object]],
    bucket: str,
    count: int,
    *,
    preserve_seeds: bool = False,
) -> None:
    available = [item for item in pool if str(item["requirement_id"]) not in selected_ids]
    chosen: list[dict[str, object]] = []
    if preserve_seeds:
        seed_items = [item for item in available if str(item["requirement_id"]) in DEFAULT_SEED_REQUIREMENT_IDS]
        chosen.extend(sorted(seed_items, key=lambda item: _natural_key(str(item["requirement_id"]))))
    remaining = [item for item in available if item not in chosen]
    chosen.extend(_round_robin(remaining, count - len(chosen)))
    if len(chosen) < count:
        raise ValueError(f"insufficient requirements for {bucket}: expected {count}, got {len(chosen)}")
    for item in chosen[:count]:
        requirement_id = str(item["requirement_id"])
        selected_ids.add(requirement_id)
        output.append(
            {
                "requirement_id": requirement_id,
                "selection_bucket": bucket,
                "selection_theme": "",
                "semantic_group": str(item["semantic_group"]),
                "evidence_kinds": json.dumps(item["evidence_kinds"], ensure_ascii=False),
                "route_status": str(item["route_status"]),
                "candidate_page_source": str(item["candidate_page_source"]),
                "selection_reason": _selection_reason(bucket, item),
            }
        )


def _round_robin(pool: list[dict[str, object]], count: int) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for item in pool:
        key = (
            str(item["semantic_group"]),
            json.dumps(item["evidence_kinds"], ensure_ascii=False),
            str(item["route_status"]),
        )
        groups[key].append(item)
    for values in groups.values():
        values.sort(key=lambda item: _natural_key(str(item["requirement_id"])))
    selected: list[dict[str, object]] = []
    keys = sorted(groups)
    while len(selected) < count and keys:
        next_keys: list[tuple[str, str, str]] = []
        for key in keys:
            values = groups[key]
            if values and len(selected) < count:
                selected.append(values.pop(0))
            if values:
                next_keys.append(key)
        keys = next_keys
    return selected


def _round_robin_by_route(pool: list[dict[str, object]], count: int) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in pool:
        groups[str(item["route_status"])].append(item)
    for values in groups.values():
        values.sort(key=lambda item: _natural_key(str(item["requirement_id"])))
    selected: list[dict[str, object]] = []
    statuses = ["candidate_with_evidence", "candidate_without_evidence", "no_candidate"]
    while len(selected) < count:
        progressed = False
        for status in statuses:
            if groups[status] and len(selected) < count:
                selected.append(groups[status].pop(0))
                progressed = True
        if not progressed:
            break
    return selected


def _requirement_topic(requirement_id: str) -> str:
    match = re.match(r"GRI\s+(\d+)", requirement_id)
    return match.group(1) if match else ""


def _boundary_sort_key(item: dict[str, object]) -> tuple[int, tuple[object, ...]]:
    evidence_kinds = set(item["evidence_kinds"])
    priority = 6
    if EvidenceKind.EXPLICIT_ZERO_STATEMENT.value in evidence_kinds:
        priority = 0
    elif item["has_guardrail"]:
        priority = 1
    elif item["has_complex_table"]:
        priority = 2
    elif item["candidate_pages"] and set(item["candidate_pages"]) != set(item["source_pages"]):
        priority = 3
    elif item["route_status"] == "candidate_without_evidence":
        priority = 4
    elif item["route_status"] == "no_candidate":
        priority = 5
    return priority, _natural_key(str(item["requirement_id"]))


def _selection_reason(bucket: str, item: dict[str, object]) -> str:
    if bucket == "all_disclosed":
        return "all current disclosed requirements are included for false-disclosed review"
    if bucket == "boundary_guardrail":
        return "high-risk evidence, guardrail, table, or route boundary"
    return "/".join(
        [str(item["semantic_group"]), json.dumps(item["evidence_kinds"], ensure_ascii=False), str(item["route_status"])]
    )


def _parse_pages(raw: str) -> list[int]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text
    values = parsed if isinstance(parsed, list) else [parsed]
    pages: list[int] = []
    for value in values:
        try:
            pages.append(int(value))
        except (TypeError, ValueError):
            continue
    return pages


def _first_non_empty(rows: list[dict[str, str]], field: str) -> str:
    return next(((row.get(field) or "").strip() for row in rows if (row.get(field) or "").strip()), "")


def _natural_key(value: str) -> tuple[object, ...]:
    return tuple(int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value))


def _bucket_order(bucket: str) -> int:
    return {
        "all_disclosed": 0,
        "partial_stratified": 1,
        "unknown_stratified": 2,
        "boundary_guardrail": 3,
    }[bucket]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a deterministic stratified holdout review sample.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--exclude-selection", type=Path)
    parser.add_argument("--combined-output", type=Path)
    args = parser.parse_args()

    rows = _read_csv(args.input_csv)
    requirement_count = len({row.get("requirement_id", "") for row in rows if row.get("requirement_id")})
    if requirement_count != 577:
        raise SystemExit(f"expected 577 unique requirements, got {requirement_count}")
    if args.exclude_selection:
        existing = _read_csv(args.exclude_selection)
        excluded_ids = {row["requirement_id"] for row in existing}
        selected = select_targeted_requirements(rows, excluded_ids)
        if args.combined_output:
            write_selection([*existing, *selected], args.combined_output)
    else:
        selected = select_stratified_requirements(rows)
    write_selection(selected, args.output_csv)
    write_summary(selected, args.summary)


if __name__ == "__main__":
    main()
