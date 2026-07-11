import json

import pytest

from src.tools.holdout_stratified_sample import (
    DEFAULT_SEED_REQUIREMENT_IDS,
    select_stratified_requirements,
    select_targeted_requirements,
)


def _row(requirement_id: str, verdict: str, *, candidate: str = "[]", source: str = "") -> dict[str, str]:
    return {
        "requirement_id": requirement_id,
        "requirement_text": f"Requirement {requirement_id}",
        "verdict": verdict,
        "review_status": "not_required" if verdict == "disclosed" else "needs_manual_review",
        "candidate_pdf_pages": candidate,
        "source_pdf_page": source,
        "candidate_page_source": "report_profile" if candidate != "[]" else "",
        "evidence_type": "substantive" if source else "",
        "quality_flags": "[]",
    }


def _baseline_rows() -> list[dict[str, str]]:
    rows = [
        _row("GRI 205-1-a", "partially_disclosed", candidate="[21]", source="21"),
        _row("GRI 205-1-b", "partially_disclosed", candidate="[21]", source="21"),
        _row("GRI 414-1-a", "partially_disclosed", candidate="[31, 32]", source="31"),
        _row("GRI 403-9-a-i", "partially_disclosed", candidate="[47]", source="47"),
        _row("GRI 418-1-a", "unknown"),
    ]
    rows.extend(_row(f"GRI D-{index:03d}", "disclosed", candidate="[1]", source="1") for index in range(15))
    rows.extend(
        _row(f"GRI P-{index:03d}", "partially_disclosed", candidate="[2]", source="2")
        for index in range(60)
    )
    rows.extend(_row(f"GRI U-{index:03d}", "unknown") for index in range(70))
    return rows


def test_selects_exact_deterministic_stratified_sample() -> None:
    rows = _baseline_rows()

    first = select_stratified_requirements(rows)
    second = select_stratified_requirements(list(reversed(rows)))

    assert first == second
    assert len(first) == 100
    assert len({row["requirement_id"] for row in first}) == 100
    bucket_counts = {
        bucket: sum(row["selection_bucket"] == bucket for row in first)
        for bucket in {row["selection_bucket"] for row in first}
    }
    assert bucket_counts == {
        "all_disclosed": 15,
        "partial_stratified": 35,
        "unknown_stratified": 40,
        "boundary_guardrail": 10,
    }
    selected_ids = {row["requirement_id"] for row in first}
    assert DEFAULT_SEED_REQUIREMENT_IDS <= selected_ids
    disclosed_ids = {row["requirement_id"] for row in rows if row["verdict"] == "disclosed"}
    assert disclosed_ids <= selected_ids


def test_unknown_contract_metadata_uses_stable_fallback() -> None:
    rows = _baseline_rows()

    selected = select_stratified_requirements(rows)
    fallback = next(row for row in selected if row["requirement_id"].startswith("GRI D-"))

    assert fallback["semantic_group"] == "unclassified"
    assert json.loads(fallback["evidence_kinds"]) == []
    assert fallback["route_status"] == "candidate_with_evidence"


def test_rejects_unexpected_disclosed_expansion() -> None:
    rows = _baseline_rows()
    rows.append(_row("GRI D-999", "disclosed", candidate="[1]", source="1"))

    with pytest.raises(ValueError, match="disclosed requirements exceed 15"):
        select_stratified_requirements(rows)


def test_selects_deterministic_non_overlapping_targeted_50() -> None:
    topics = {
        "ohs_kpi": "403",
        "supplier_environment_social_assessment": "414",
        "energy_ghg_kpi": "305",
        "employee_turnover_parental_leave": "401",
        "zero_event_compliance": "417",
    }
    rows: list[dict[str, str]] = []
    for theme, topic in topics.items():
        for index in range(15):
            route = index % 3
            rows.append(
                _row(
                    f"GRI {topic}-{index}-a",
                    "unknown",
                    candidate="[]" if route == 2 else f"[{index + 1}]",
                    source="" if route else str(index + 1),
                )
            )
    excluded = {f"GRI {topic}-0-a" for topic in topics.values()}

    first = select_targeted_requirements(rows, excluded)
    second = select_targeted_requirements(list(reversed(rows)), excluded)

    assert first == second
    assert len(first) == 50
    assert not ({row["requirement_id"] for row in first} & excluded)
    assert {
        theme: sum(row["selection_theme"] == theme for row in first)
        for theme in topics
    } == {
        "ohs_kpi": 12,
        "supplier_environment_social_assessment": 4,
        "energy_ghg_kpi": 12,
        "employee_turnover_parental_leave": 11,
        "zero_event_compliance": 11,
    }
    for theme in topics:
        statuses = {row["route_status"] for row in first if row["selection_theme"] == theme}
        assert statuses == {"candidate_with_evidence", "candidate_without_evidence", "no_candidate"}
