from __future__ import annotations

import argparse
import ast
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from src.standards.evidence_contracts import get_requirement_contract
from src.standards.leaf_sufficiency import get_leaf_sufficiency_rule
from src.standards.compilation_guardrails import get_compilation_guardrails


REMEDIATION_MANIFEST_COLUMNS = [
    "requirement_id",
    "current_verdict",
    "suggested_verdict",
    "issue_type",
    "current_source_pdf_pages",
    "correct_pdf_pages",
    "semantic_group",
    "evidence_kinds",
    "remediation_group",
]


@dataclass(frozen=True)
class FirstPassQualityResult:
    first_pass_disclosed_count: int
    first_pass_partial_count: int
    first_pass_unknown_count: int
    first_pass_recall: float
    false_disclosed_count: int
    wrong_source_page_count: int
    unknown_leakage_count: int
    after_rules_delta_disclosed: int
    after_rules_delta_partial: int
    after_rules_delta_unknown: int
    manual_gold_available: bool
    profile_route_valid_evidence_rate: float | None
    cross_leaf_missing_items_count: int
    guardrail_as_evidence_count: int


def compare_first_pass_to_after_rules(
    current_csv: str | Path,
    after_rules_csv: str | Path,
) -> FirstPassQualityResult:
    current_rows = _read_first_rows_by_requirement(Path(current_csv))
    after_rows = _read_first_rows_by_requirement(Path(after_rules_csv))

    first_counts = _verdict_counts(current_rows.values())
    after_counts = _verdict_counts(after_rows.values())

    unknown_leakage = 0
    false_disclosed = 0
    wrong_source_page = 0
    recall_denominator = 0
    recall_hits = 0

    for row in current_rows.values():
        verdict = _cell(row, "verdict")
        suggested_verdict = _cell(row, "suggested_verdict")
        issue_type = _cell(row, "issue_type")
        manual_label = _cell(row, "manual_label")

        expected_has_evidence = suggested_verdict in {"disclosed", "partially_disclosed"}
        if expected_has_evidence:
            recall_denominator += 1
            if verdict != "unknown":
                recall_hits += 1

        if (
            issue_type == "missed_evidence"
            or "漏检" in manual_label
            or (verdict == "unknown" and expected_has_evidence)
        ):
            unknown_leakage += 1

        if issue_type == "false_disclosed" or (verdict == "disclosed" and suggested_verdict and suggested_verdict != "disclosed"):
            false_disclosed += 1

        if issue_type == "wrong_source_page" or _has_wrong_source_page(row):
            wrong_source_page += 1

    first_recall = recall_hits / recall_denominator if recall_denominator else 0.0

    return FirstPassQualityResult(
        first_pass_disclosed_count=first_counts["disclosed"],
        first_pass_partial_count=first_counts["partially_disclosed"],
        first_pass_unknown_count=first_counts["unknown"],
        first_pass_recall=first_recall,
        false_disclosed_count=false_disclosed,
        wrong_source_page_count=wrong_source_page,
        unknown_leakage_count=unknown_leakage,
        after_rules_delta_disclosed=after_counts["disclosed"] - first_counts["disclosed"],
        after_rules_delta_partial=after_counts["partially_disclosed"] - first_counts["partially_disclosed"],
        after_rules_delta_unknown=after_counts["unknown"] - first_counts["unknown"],
        manual_gold_available=_manual_gold_available(current_rows, current_rows),
        profile_route_valid_evidence_rate=_profile_route_valid_evidence_rate(current_rows, current_rows),
        cross_leaf_missing_items_count=sum(
            _cell(row, "issue_type") == "cross_leaf_missing_items" for row in current_rows.values()
        ),
        guardrail_as_evidence_count=sum(
            _cell(row, "issue_type") == "guardrail_as_evidence" for row in current_rows.values()
        ),
    )


def summarize_quality(first_rows: list[dict[str, str]], reviewed_rows: list[dict[str, str]]) -> FirstPassQualityResult:
    first_by_requirement = _aggregate_rows_from_iterable(first_rows)
    reviewed_by_requirement = _first_rows_from_iterable(reviewed_rows)
    first_by_requirement = {
        requirement_id: first_by_requirement[requirement_id]
        for requirement_id in reviewed_by_requirement
        if requirement_id in first_by_requirement
    }

    first_counts = _verdict_counts(first_by_requirement.values())
    reviewed_counts = _verdict_counts(reviewed_by_requirement.values())

    unknown_leakage = 0
    false_disclosed = 0
    wrong_source_page = 0
    recall_denominator = 0
    recall_hits = 0
    manual_gold_available = _manual_gold_available(first_by_requirement, reviewed_by_requirement)

    for requirement_id, row in first_by_requirement.items():
        reviewed = reviewed_by_requirement.get(requirement_id, {})
        verdict = _cell(row, "verdict")
        suggested_verdict = _cell(reviewed, "suggested_verdict")
        issue_type = _cell(reviewed, "issue_type")

        expected_has_evidence = suggested_verdict in {"disclosed", "partially_disclosed"}
        if expected_has_evidence:
            recall_denominator += 1
            if verdict != "unknown":
                recall_hits += 1

        if verdict == "unknown" and expected_has_evidence:
            unknown_leakage += 1

        if verdict == "disclosed" and suggested_verdict and suggested_verdict != "disclosed":
            false_disclosed += 1

        if manual_gold_available:
            source_pages = set(_parse_pages(_cell(row, "source_pdf_pages") or _cell(row, "source_pdf_page")))
            correct_pages = set(_parse_pages(_cell(reviewed, "correct_pdf_pages")))
            if source_pages != correct_pages:
                wrong_source_page += 1
        elif issue_type == "wrong_source_page" or _has_wrong_source_page({**row, **reviewed}):
            wrong_source_page += 1

    first_recall = recall_hits / recall_denominator if recall_denominator else 0.0
    return FirstPassQualityResult(
        first_pass_disclosed_count=first_counts["disclosed"],
        first_pass_partial_count=first_counts["partially_disclosed"],
        first_pass_unknown_count=first_counts["unknown"],
        first_pass_recall=first_recall,
        false_disclosed_count=false_disclosed,
        wrong_source_page_count=wrong_source_page,
        unknown_leakage_count=unknown_leakage,
        after_rules_delta_disclosed=reviewed_counts["disclosed"] - first_counts["disclosed"],
        after_rules_delta_partial=reviewed_counts["partially_disclosed"] - first_counts["partially_disclosed"],
        after_rules_delta_unknown=reviewed_counts["unknown"] - first_counts["unknown"],
        manual_gold_available=manual_gold_available,
        profile_route_valid_evidence_rate=_profile_route_valid_evidence_rate(
            first_by_requirement,
            reviewed_by_requirement,
        ),
        cross_leaf_missing_items_count=_cross_leaf_missing_items_count(
            first_by_requirement,
            reviewed_by_requirement,
        ),
        guardrail_as_evidence_count=sum(
            _cell(row, "issue_type") == "guardrail_as_evidence" for row in reviewed_by_requirement.values()
        ),
    )


def summarize_quality_csv(
    first_pass_csv: str | Path,
    reviewed_csv: str | Path,
) -> FirstPassQualityResult:
    return summarize_quality(
        _read_rows(Path(first_pass_csv)),
        _read_rows(Path(reviewed_csv)),
    )


def build_remediation_manifest_rows(
    first_rows: list[dict[str, str]],
    reviewed_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    first_by_requirement = _aggregate_rows_from_iterable(first_rows)
    reviewed_by_requirement = _first_rows_from_iterable(reviewed_rows)
    output: list[dict[str, str]] = []
    for requirement_id in reviewed_by_requirement:
        reviewed = reviewed_by_requirement[requirement_id]
        first = first_by_requirement.get(requirement_id)
        if first is None:
            raise ValueError(f"reviewed requirement missing from first-pass CSV: {requirement_id}")
        contract = get_requirement_contract(requirement_id)
        semantic_group = contract.semantic_group.value if contract and contract.semantic_group else "unclassified"
        evidence_kinds = sorted(kind.value for kind in contract.evidence_kinds) if contract else []
        issue_type = _cell(reviewed, "issue_type")
        output.append(
            {
                "requirement_id": requirement_id,
                "current_verdict": _cell(first, "verdict"),
                "suggested_verdict": _cell(reviewed, "suggested_verdict"),
                "issue_type": issue_type,
                "current_source_pdf_pages": _cell(first, "source_pdf_pages") or "[]",
                "correct_pdf_pages": _cell(reviewed, "correct_pdf_pages") or "[]",
                "semantic_group": semantic_group,
                "evidence_kinds": json.dumps(evidence_kinds, ensure_ascii=False),
                "remediation_group": _remediation_group(issue_type),
            }
        )
    return output


def write_remediation_manifest(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REMEDIATION_MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _remediation_group(issue_type: str) -> str:
    return {
        "false_disclosed": "precision_gate",
        "wrong_source_page": "source_promotion",
        "invalid_evidence": "source_promotion",
        "missed_evidence": "recall",
        "over_strict_unknown": "recall",
        "cross_leaf_missing_items": "leaf_sufficiency",
        "acceptable": "regression_control",
    }.get(issue_type, "manual_review")


def _manual_gold_available(
    first_rows: dict[str, dict[str, str]],
    reviewed_rows: dict[str, dict[str, str]],
) -> bool:
    return bool(first_rows) and set(first_rows) == set(reviewed_rows) and all(
        _cell(row, "manual_label")
        and _cell(row, "suggested_verdict")
        and _cell(row, "issue_type")
        for row in reviewed_rows.values()
    )


def _profile_route_valid_evidence_rate(
    first_rows: dict[str, dict[str, str]],
    reviewed_rows: dict[str, dict[str, str]],
) -> float | None:
    if not _manual_gold_available(first_rows, reviewed_rows):
        return None
    routed = [
        requirement_id
        for requirement_id, row in first_rows.items()
        if (
            "report_profile" in _cell(row, "candidate_page_source")
            and bool(_parse_pages(_cell(row, "source_pdf_pages") or _cell(row, "source_pdf_page")))
        )
        or (
            not _cell(row, "candidate_page_source")
            and _cell(row, "current_route_status") == "candidate_with_evidence"
        )
    ]
    if not routed:
        return None
    valid = sum(
        bool(
            set(_parse_pages(_cell(first_rows[requirement_id], "source_pdf_pages") or _cell(first_rows[requirement_id], "source_pdf_page")))
            & set(_parse_pages(_cell(reviewed_rows[requirement_id], "correct_pdf_pages")))
        )
        for requirement_id in routed
    )
    return valid / len(routed)


def _cross_leaf_missing_items_count(
    first_rows: dict[str, dict[str, str]],
    reviewed_rows: dict[str, dict[str, str]],
) -> int:
    count = 0
    for requirement_id, reviewed in reviewed_rows.items():
        if _cell(reviewed, "issue_type") != "cross_leaf_missing_items":
            continue
        rule = get_leaf_sufficiency_rule(requirement_id)
        if rule is None:
            count += 1
            continue
        actual = tuple(_parse_text_list(_cell(first_rows.get(requirement_id, {}), "missing_items")))
        guardrail_items = {
            item
            for guardrail in get_compilation_guardrails(requirement_id)
            for item in guardrail.missing_item_templates
        }
        actual = tuple(item for item in actual if item not in guardrail_items)
        if actual != rule.missing_item_templates:
            count += 1
    return count


def _parse_text_list(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [raw]
    return [str(item) for item in parsed] if isinstance(parsed, list) else [str(parsed)]


def _read_first_rows_by_requirement(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            requirement_id = _cell(row, "requirement_id")
            if not requirement_id or requirement_id in rows:
                continue
            rows[requirement_id] = {key: value or "" for key, value in row.items()}
    return rows


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {key: value or "" for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _first_rows_from_iterable(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    first_rows: dict[str, dict[str, str]] = {}
    for row in rows:
        requirement_id = _cell(row, "requirement_id")
        if not requirement_id or requirement_id in first_rows:
            continue
        first_rows[requirement_id] = {key: str(value or "") for key, value in row.items()}
    return first_rows


def _aggregate_rows_from_iterable(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        requirement_id = _cell(row, "requirement_id")
        if requirement_id:
            grouped.setdefault(requirement_id, []).append(row)
    aggregated: dict[str, dict[str, str]] = {}
    for requirement_id, requirement_rows in grouped.items():
        base = {key: str(value or "") for key, value in requirement_rows[0].items()}
        source_pages = sorted(
            {
                page
                for row in requirement_rows
                for page in _parse_pages(_cell(row, "source_pdf_pages") or _cell(row, "source_pdf_page"))
            }
        )
        candidate_sources = sorted(
            {_cell(row, "candidate_page_source") for row in requirement_rows} - {""}
        )
        base["source_pdf_pages"] = json.dumps(source_pages)
        base["candidate_page_source"] = "+".join(candidate_sources)
        aggregated[requirement_id] = base
    return aggregated


def _verdict_counts(rows: object) -> dict[str, int]:
    counts = {"disclosed": 0, "partially_disclosed": 0, "unknown": 0}
    for row in rows:
        verdict = _cell(row, "verdict")
        if verdict in counts:
            counts[verdict] += 1
    return counts


def _has_wrong_source_page(row: dict[str, str]) -> bool:
    correct_pages = _parse_pages(_cell(row, "correct_pdf_pages"))
    if not correct_pages:
        return False
    source_pages = _parse_pages(_cell(row, "source_pdf_pages") or _cell(row, "source_pdf_page"))
    if not source_pages:
        return False
    return not set(source_pages).issubset(set(correct_pages))


def _parse_pages(raw: str) -> list[int]:
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        parsed = raw

    if isinstance(parsed, int):
        return [parsed]
    if isinstance(parsed, list | tuple | set):
        values = parsed
    else:
        values = str(parsed).replace(";", ",").split(",")

    pages: list[int] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        try:
            pages.append(int(float(text)))
        except ValueError:
            continue
    return pages


def _cell(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare first-pass and after-rules review CSV quality.")
    parser.add_argument("current_csv", type=Path)
    parser.add_argument("after_rules_csv", type=Path)
    parser.add_argument("--manual-reviewed", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--remediation-manifest-output", type=Path)
    args = parser.parse_args()

    if args.manual_reviewed:
        result = summarize_quality_csv(args.current_csv, args.after_rules_csv)
    else:
        result = compare_first_pass_to_after_rules(args.current_csv, args.after_rules_csv)
    output = json.dumps(asdict(result), ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(output + "\n", encoding="utf-8")
    if args.remediation_manifest_output:
        if not args.manual_reviewed:
            parser.error("--remediation-manifest-output requires --manual-reviewed")
        write_remediation_manifest(
            build_remediation_manifest_rows(_read_rows(args.current_csv), _read_rows(args.after_rules_csv)),
            args.remediation_manifest_output,
        )
    print(output)


if __name__ == "__main__":
    main()
