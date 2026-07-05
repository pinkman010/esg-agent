from __future__ import annotations

import argparse
import ast
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path


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
    )


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
    source_pages = _parse_pages(_cell(row, "source_pdf_page"))
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
    args = parser.parse_args()

    result = compare_first_pass_to_after_rules(args.current_csv, args.after_rules_csv)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
