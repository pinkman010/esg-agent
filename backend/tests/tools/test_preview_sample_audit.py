from pathlib import Path

from src.tools.preview_sample_audit import build_preview_sample_rows


def test_preview_sample_rows_flag_missing_anchor(tmp_path: Path):
    source = tmp_path / "review.csv"
    source.write_text(
        "requirement_id,verdict,evidence_preview,source_pdf_page,candidate_page_source,evidence_type\n"
        "GRI 414-1-a,disclosed,页眉 目录 相邻表格,31,report_profile,substantive\n"
        "GRI 403-9-a-i,disclosed,员工因工死亡人数 人 0,47,report_profile,substantive\n",
        encoding="utf-8",
    )

    rows = build_preview_sample_rows(
        source,
        anchors={
            "GRI 414-1-a": ["供应商", "社会评价"],
            "GRI 403-9-a-i": ["死亡人数", "0"],
        },
    )

    assert rows[0]["preview_anchor_status"] == "missing_anchor"
    assert rows[1]["preview_anchor_status"] == "anchor_found"
