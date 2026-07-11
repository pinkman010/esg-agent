from src.tools.review_csv_export import export_review_rows


def test_export_review_rows_preserves_contract_fields():
    assessments = [
        {
            "requirement_id": "GRI 2-1-a",
            "verdict": "disclosed",
            "review_status": "not_required",
            "rationale": "Legal name is disclosed.",
            "missing_items": [],
            "evidence": [
                {
                    "source_pdf_page": 1,
                    "source_report_page": None,
                    "candidate_pdf_pages": [1, 3],
                    "candidate_report_pages": [None, 2],
                    "page_label": "PDF 第 1 页",
                    "retrieval_strategy": "index_page_bounded",
                    "candidate_page_source": "report_profile",
                    "evidence_type": "substantive",
                    "quality_flags": ["digital_text"],
                    "requires_ocr": False,
                    "requires_vlm": False,
                    "needs_ocr_or_vlm": False,
                    "evidence_preview": "金风科技股份有限公司",
                    "source_text": "金风科技股份有限公司",
                }
            ],
        }
    ]

    rows = export_review_rows(assessments)

    assert rows == [
        {
            "requirement_id": "GRI 2-1-a",
            "verdict": "disclosed",
            "review_status": "not_required",
            "rationale": "Legal name is disclosed.",
            "missing_items": "[]",
            "source_pdf_page": "1",
            "source_report_page": "",
            "candidate_pdf_pages": "[1, 3]",
            "candidate_report_pages": "[null, 2]",
            "page_label": "PDF 第 1 页",
            "retrieval_strategy": "index_page_bounded",
            "candidate_page_source": "report_profile",
            "evidence_type": "substantive",
            "quality_flags": '["digital_text"]',
            "requires_ocr": "False",
            "requires_vlm": "False",
            "needs_ocr_or_vlm": "False",
            "evidence_preview": "金风科技股份有限公司",
            "source_text": "金风科技股份有限公司",
        }
    ]


def test_export_review_rows_outputs_unknown_without_evidence():
    rows = export_review_rows(
        [
            {
                "requirement_id": "GRI 2-1-b",
                "verdict": "unknown",
                "review_status": "needs_manual_review",
                "missing_items": ["ownership nature"],
                "evidence": [],
            }
        ]
    )

    assert rows[0]["requirement_id"] == "GRI 2-1-b"
    assert rows[0]["source_pdf_page"] == ""
    assert rows[0]["candidate_pdf_pages"] == ""
    assert rows[0]["missing_items"] == '["ownership nature"]'


def test_export_review_rows_defaults_substantive_evidence_type_for_real_evidence():
    rows = export_review_rows(
        [
            {
                "requirement_id": "GRI 203-2-b",
                "verdict": "partially_disclosed",
                "review_status": "needs_manual_review",
                "evidence": [
                    {
                        "source_pdf_page": 42,
                        "source_text": "社区项目",
                    }
                ],
            }
        ]
    )

    assert rows[0]["evidence_type"] == "substantive"


def test_export_review_rows_sorts_evidence_by_candidate_page_order():
    rows = export_review_rows(
        [
            {
                "requirement_id": "GRI 2-25-a",
                "verdict": "partially_disclosed",
                "review_status": "needs_manual_review",
                "evidence": [
                    {"source_pdf_page": 53, "candidate_pdf_pages": [32, 53, 59]},
                    {"source_pdf_page": 59, "candidate_pdf_pages": [32, 53, 59]},
                    {"source_pdf_page": 32, "candidate_pdf_pages": [32, 53, 59]},
                ],
            }
        ]
    )

    assert [row["source_pdf_page"] for row in rows] == ["32", "53", "59"]
