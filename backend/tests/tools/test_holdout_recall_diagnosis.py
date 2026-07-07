from pathlib import Path

from src.tools.holdout_recall_diagnosis import build_recall_diagnosis_rows


def test_recall_diagnosis_classifies_route_missing(tmp_path: Path):
    source = tmp_path / "first_pass.csv"
    source.write_text(
        "requirement_id,verdict,review_status,candidate_pdf_pages,source_pdf_page,retrieval_strategy,evidence_type,evidence_preview\n"
        "GRI 205-1-a,unknown,needs_manual_review,[],10,global_no_index,substantive,policy text\n",
        encoding="utf-8",
    )

    rows = build_recall_diagnosis_rows(
        first_pass_csv=source,
        manual_gold={
            "GRI 205-1-a": {
                "issue_type": "unknown_leakage",
                "correct_pdf_pages": [21],
                "evidence_kind": "management_mechanism",
            }
        },
    )

    assert rows[0]["route_failure_reason"] == "candidate_pages_missing"
    assert rows[0]["suggested_profile_route"] == "[21]"


def test_recall_diagnosis_classifies_keyword_miss(tmp_path: Path):
    source = tmp_path / "first_pass.csv"
    source.write_text(
        "requirement_id,verdict,review_status,candidate_pdf_pages,source_pdf_page,retrieval_strategy,evidence_type,evidence_preview\n"
        'GRI 414-1-a,unknown,needs_manual_review,"[31, 32]",,index_page_bounded,,\n',
        encoding="utf-8",
    )

    rows = build_recall_diagnosis_rows(
        first_pass_csv=source,
        manual_gold={
            "GRI 414-1-a": {
                "issue_type": "unknown_leakage",
                "correct_pdf_pages": [31, 32],
                "evidence_kind": "kpi_value",
            }
        },
    )

    assert rows[0]["route_failure_reason"] == "candidate_pages_present_keyword_miss"


def test_recall_diagnosis_classifies_matrix_conservative(tmp_path: Path):
    source = tmp_path / "first_pass.csv"
    source.write_text(
        "requirement_id,verdict,review_status,candidate_pdf_pages,source_pdf_page,retrieval_strategy,evidence_type,evidence_preview\n"
        "GRI 403-9-a-i,unknown,needs_manual_review,[47],47,index_page_bounded,substantive,death rate 0\n",
        encoding="utf-8",
    )

    rows = build_recall_diagnosis_rows(
        first_pass_csv=source,
        manual_gold={
            "GRI 403-9-a-i": {
                "issue_type": "unknown_leakage",
                "correct_pdf_pages": [47],
                "evidence_kind": "kpi_value",
            }
        },
    )

    assert rows[0]["route_failure_reason"] == "evidence_found_matrix_conservative"
