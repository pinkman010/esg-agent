from pathlib import Path

from src.tools.holdout_review_pack import build_review_pack_rows, build_route_improvement_rows


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


def test_build_route_improvement_rows_uses_profile_candidates_when_first_pass_has_no_evidence(tmp_path: Path):
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
    profile = tmp_path / "profile.json"
    profile.write_text(
        """{
          "report_id": "goldwind_2024",
          "company_name": "Goldwind",
          "report_year": 2024,
          "pdf_file": "goldwind.pdf",
          "total_pdf_pages": 52,
          "page_numbering": {"report_index_pdf_page": 50, "report_index_report_page": 96, "total_pdf_pages": 52},
          "gri_index": {"pdf_pages": [50, 51]},
          "sections": [],
          "index_note_pages": [],
          "assurance_pages": [],
          "requirement_routes": {
            "GRI 414-1-a": {"candidate_pdf_pages": [31, 32], "kpi_table_pages": [], "metric_terms": ["供应商"]}
          }
        }""",
        encoding="utf-8",
    )

    rows = build_route_improvement_rows(gold, first_pass, profile)

    assert rows[0]["profile_candidate_pdf_pages"] == "[31, 32]"
    assert rows[0]["route_status"] == "candidate_without_evidence"


def test_build_review_pack_rows_marks_manual_review_need(tmp_path: Path):
    route_improvement = tmp_path / "routes.csv"
    route_improvement.write_text(
        "requirement_id,issue_type,evidence_kind,correct_pdf_pages,suggested_profile_route,before_verdict,before_review_status,before_source_pdf_pages,before_candidate_pdf_pages,profile_candidate_pdf_pages,route_status,evidence_preview\n"
        "GRI 414-1-a,unknown_leakage,kpi_value,\"[31, 32]\",\"[31, 32]\",unknown,needs_manual_review,[],[],\"[31, 32]\",candidate_without_evidence,\n",
        encoding="utf-8",
    )

    rows = build_review_pack_rows(route_improvement)

    assert rows[0]["manual_check_required"] == "true"
    assert rows[0]["manual_check_focus"] == "route_and_preview"
