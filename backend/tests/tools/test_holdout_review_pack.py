from pathlib import Path

from src.tools.holdout_review_pack import build_route_improvement_rows


def test_build_route_improvement_rows_joins_gold_and_first_pass(tmp_path: Path):
    gold = tmp_path / "gold.csv"
    gold.write_text(
        "requirement_id,issue_type,correct_pdf_pages,evidence_kind,suggested_profile_route\n"
        "GRI 414-1-a,unknown_leakage,\"[31, 32]\",kpi_value,\"[31, 32]\"\n",
        encoding="utf-8",
    )
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,verdict,review_status,source_pdf_page,candidate_pdf_pages,evidence_preview\n"
        "GRI 414-1-a,unknown,needs_manual_review,,[],\n",
        encoding="utf-8",
    )

    rows = build_route_improvement_rows(gold, first_pass)

    assert rows[0]["requirement_id"] == "GRI 414-1-a"
    assert rows[0]["before_verdict"] == "unknown"
    assert rows[0]["correct_pdf_pages"] == "[31, 32]"
    assert rows[0]["route_status"] == "missing_candidate"
