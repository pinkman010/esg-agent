from pathlib import Path

from src.tools.holdout_review_pack import (
    build_review_pack_rows,
    build_route_improvement_rows,
    build_stratified_review_pack_rows,
    write_review_pack_rows,
)


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


def test_build_route_improvement_rows_aggregates_review_context_per_requirement(tmp_path: Path):
    diagnosis = tmp_path / "diagnosis.csv"
    diagnosis.write_text(
        "requirement_id,issue_type,correct_pdf_pages,evidence_kind,suggested_profile_route\n"
        'GRI 414-1-a,unknown_leakage,"[31]",kpi_value,"[31, 32]"\n',
        encoding="utf-8",
    )
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,requirement_text,verdict,review_status,source_pdf_page,candidate_pdf_pages,rationale,missing_items,evidence_preview\n"
        'GRI 414-1-a,new supplier social screening percentage,partially_disclosed,needs_manual_review,31,"[31, 32]",directional supplier audit evidence,"[\"\"new supplier denominator\"\"]",social audit row\n'
        'GRI 414-1-a,new supplier social screening percentage,partially_disclosed,needs_manual_review,32,"[31, 32]",directional supplier audit evidence,"[\"\"new supplier denominator\"\"]",adjacent page\n',
        encoding="utf-8",
    )

    rows = build_route_improvement_rows(diagnosis, first_pass)

    assert len(rows) == 1
    assert rows[0]["requirement_text"] == "new supplier social screening percentage"
    assert rows[0]["verdict"] == "partially_disclosed"
    assert rows[0]["review_status"] == "needs_manual_review"
    assert rows[0]["source_pdf_pages"] == "[31, 32]"
    assert rows[0]["rationale"] == "directional supplier audit evidence"
    assert rows[0]["missing_items"] == '["new supplier denominator"]'


def test_build_route_improvement_rows_falls_back_to_requirement_text_mapping(tmp_path: Path):
    diagnosis = tmp_path / "diagnosis.csv"
    diagnosis.write_text(
        "requirement_id,issue_type,correct_pdf_pages,evidence_kind,suggested_profile_route\n"
        "GRI 418-1-a,acceptable,[], ,[]\n",
        encoding="utf-8",
    )
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,requirement_text,verdict,review_status,source_pdf_page,candidate_pdf_pages,rationale,missing_items,evidence_preview\n"
        'GRI 418-1-a,,unknown,needs_manual_review,,,no valid complaint evidence,"[""complaint total""]",\n',
        encoding="utf-8",
    )

    rows = build_route_improvement_rows(
        diagnosis,
        first_pass,
        requirement_texts={"GRI 418-1-a": "substantiated customer privacy complaints"},
    )

    assert rows[0]["requirement_text"] == "substantiated customer privacy complaints"


def test_route_improvement_marks_profile_route_without_evidence_as_keyword_miss(tmp_path: Path):
    diagnosis = tmp_path / "diagnosis.csv"
    diagnosis.write_text(
        "requirement_id,issue_type,correct_pdf_pages,evidence_kind,suggested_profile_route,route_failure_reason\n"
        "GRI 205-1-a,keyword_miss,[21],management_mechanism,[21],candidate_pages_present_keyword_miss\n",
        encoding="utf-8",
    )
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,verdict,review_status,source_pdf_page,candidate_pdf_pages,candidate_page_source,evidence_preview\n"
        "GRI 205-1-a,unknown,needs_manual_review,,,,\n",
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
            "GRI 205-1-a": {"candidate_pdf_pages": [21], "kpi_table_pages": [], "metric_terms": ["反腐败", "审计"]}
          }
        }""",
        encoding="utf-8",
    )

    rows = build_route_improvement_rows(diagnosis, first_pass, profile)

    assert rows[0]["profile_candidate_pdf_pages"] == "[21]"
    assert rows[0]["route_status"] == "candidate_without_evidence"
    assert rows[0]["route_failure_reason"] == "candidate_pages_present_keyword_miss"


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


def test_build_review_pack_rows_includes_aggregated_assessment_context(tmp_path: Path):
    route_improvement = tmp_path / "routes.csv"
    route_improvement.write_text(
        "requirement_id,requirement_text,verdict,review_status,source_pdf_pages,rationale,missing_items,issue_type,evidence_kind,correct_pdf_pages,suggested_profile_route,before_verdict,before_review_status,before_source_pdf_pages,before_candidate_pdf_pages,profile_candidate_pdf_pages,route_status,evidence_preview\n"
        'GRI 414-1-a,new supplier social screening percentage,partially_disclosed,needs_manual_review,"[31]",directional supplier audit evidence,"[""new supplier denominator""]",acceptable,kpi_value,"[31]","[31, 32]",partially_disclosed,needs_manual_review,"[31]","[31, 32]","[31, 32]",candidate_with_evidence,social audit row\n',
        encoding="utf-8",
    )

    rows = build_review_pack_rows(route_improvement)

    assert rows[0]["requirement_text"] == "new supplier social screening percentage"
    assert rows[0]["verdict"] == "partially_disclosed"
    assert rows[0]["review_status"] == "needs_manual_review"
    assert rows[0]["source_pdf_pages"] == "[31]"
    assert rows[0]["rationale"] == "directional supplier audit evidence"
    assert rows[0]["missing_items"] == '["new supplier denominator"]'


def test_build_review_pack_rows_separates_compilation_guardrails_from_leaf_missing_items(tmp_path: Path):
    route_improvement = tmp_path / "routes.csv"
    route_improvement.write_text(
        "requirement_id,requirement_text,verdict,review_status,source_pdf_pages,rationale,missing_items,issue_type,evidence_kind,correct_pdf_pages,suggested_profile_route,before_verdict,before_review_status,before_source_pdf_pages,before_candidate_pdf_pages,profile_candidate_pdf_pages,route_status,evidence_preview\n"
        'GRI 403-9-a-i,work-related injury fatalities,partially_disclosed,needs_manual_review,"[47]",fatality count only,"[""employee fatality rate"", ""commuting incidents included only when transport is organization-arranged"", ""rates based on 200000 or 1000000 hours worked""]",acceptable,kpi_value,"[47]","[47]",partially_disclosed,needs_manual_review,"[47]","[47]","[47]",candidate_with_evidence,fatality row\n',
        encoding="utf-8",
    )

    rows = build_review_pack_rows(route_improvement)

    assert rows[0]["missing_items"] == '["employee fatality rate"]'
    assert rows[0]["guardrail_items"] == (
        '["commuting incidents included only when transport is organization-arranged", '
        '"rates based on 200000 or 1000000 hours worked"]'
    )

    output = tmp_path / "review-pack.csv"
    write_review_pack_rows(rows, output)

    assert "guardrail_items" in output.read_text(encoding="utf-8-sig").splitlines()[0]


def test_build_review_pack_rows_clears_stale_diagnosis_when_unknown_has_no_evidence(tmp_path: Path):
    route_improvement = tmp_path / "routes.csv"
    route_improvement.write_text(
        "requirement_id,issue_type,evidence_kind,correct_pdf_pages,suggested_profile_route,before_verdict,before_review_status,before_source_pdf_pages,before_candidate_pdf_pages,profile_candidate_pdf_pages,route_status,evidence_preview\n"
        "GRI 418-1-a,false_disclosed,explicit_zero_statement,[],[],unknown,needs_manual_review,[],[],[],missing_candidate,\n",
        encoding="utf-8",
    )

    rows = build_review_pack_rows(route_improvement)

    assert rows[0]["issue_type"] == "acceptable"
    assert rows[0]["evidence_kind"] == ""
    assert rows[0]["manual_check_focus"] == "no_evidence_boundary"


def test_build_stratified_review_pack_joins_selection_and_aggregates_evidence(tmp_path: Path):
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,requirement_text,verdict,review_status,source_pdf_page,candidate_pdf_pages,evidence_type,evidence_preview,rationale,missing_items\n"
        'GRI 414-1-a,new supplier screening,partially_disclosed,needs_manual_review,31,"[31, 32]",substantive,social audit KPI,directional evidence,"[""new supplier denominator""]"\n'
        'GRI 414-1-a,new supplier screening,partially_disclosed,needs_manual_review,32,"[31, 32]",substantive,adjacent candidate,directional evidence,"[""new supplier denominator""]"\n'
        "GRI 999-1-a,excluded requirement,unknown,needs_manual_review,,,,,,\n",
        encoding="utf-8",
    )
    selection = tmp_path / "selection.csv"
    selection.write_text(
        "requirement_id,selection_bucket,semantic_group,evidence_kinds,route_status,candidate_page_source,selection_reason\n"
        'GRI 414-1-a,partial_stratified,supplier_assessment,"[""kpi_value""]",candidate_with_evidence,report_profile,stratified\n',
        encoding="utf-8",
    )

    rows = build_stratified_review_pack_rows(first_pass, selection)

    assert len(rows) == 1
    assert rows[0]["requirement_text"] == "new supplier screening"
    assert rows[0]["candidate_pdf_pages"] == "[31, 32]"
    assert rows[0]["source_pdf_pages"] == "[31, 32]"
    assert rows[0]["evidence_type"] == '["substantive"]'
    assert rows[0]["evidence_kind"] == '["kpi_value"]'
    assert rows[0]["selection_bucket"] == "partial_stratified"
    assert rows[0]["selection_reason"] == "stratified"


def test_review_pack_preserves_targeted_selection_theme(tmp_path: Path):
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,verdict,review_status,source_pdf_page,candidate_pdf_pages,candidate_page_source,evidence_preview\n"
        'GRI 403-9-a-i,partially_disclosed,needs_manual_review,47,[47],report_profile,employee fatality count\n',
        encoding="utf-8",
    )
    selection = tmp_path / "selection.csv"
    selection.write_text(
        "requirement_id,selection_bucket,selection_theme,semantic_group,evidence_kinds,route_status,candidate_page_source,selection_reason\n"
        'GRI 403-9-a-i,targeted_50,ohs_kpi,ohs_kpi,[\"kpi_value\"],candidate_with_evidence,report_profile,targeted\n',
        encoding="utf-8",
    )

    rows = build_stratified_review_pack_rows(
        first_pass,
        selection,
        requirement_texts={"GRI 403-9-a-i": "number and rate of employee fatalities"},
    )

    assert rows[0]["selection_theme"] == "ohs_kpi"
    assert rows[0]["requirement_text"] == "number and rate of employee fatalities"
    assert rows[0]["correct_pdf_pages"] == ""
    assert rows[0]["manual_label"] == ""


def test_build_stratified_review_pack_clears_unknown_no_evidence_metadata(tmp_path: Path):
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,requirement_text,verdict,review_status,source_pdf_page,candidate_pdf_pages,evidence_type,evidence_preview,rationale,missing_items\n"
        "GRI 418-1-a,privacy complaints,unknown,needs_manual_review,,[],explicit_zero_statement,stale preview,no evidence,[]\n",
        encoding="utf-8",
    )
    selection = tmp_path / "selection.csv"
    selection.write_text(
        "requirement_id,selection_bucket,semantic_group,evidence_kinds,route_status,candidate_page_source,selection_reason\n"
        'GRI 418-1-a,boundary_guardrail,zero_event_compliance,"[""explicit_zero_statement""]",no_candidate,,zero-event boundary\n',
        encoding="utf-8",
    )

    rows = build_stratified_review_pack_rows(first_pass, selection)

    assert rows[0]["source_pdf_pages"] == "[]"
    assert rows[0]["evidence_type"] == ""
    assert rows[0]["evidence_kind"] == ""
    assert rows[0]["evidence_preview"] == ""
