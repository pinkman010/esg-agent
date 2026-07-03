from src.agents.disclosure_agent import DisclosureAgent
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, ReviewStatus
from src.domain.models import DisclosureTask, DocumentChunk


def make_task():
    return DisclosureTask(
        task_id="task-1",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 302",
        requirement_id="GRI 302-1-a",
        requirement_text="Disclose energy consumption.",
        keywords=["energy"],
    )


def test_disclosure_agent_generates_assessment_from_evidence_without_model_call():
    chunk = DocumentChunk(
        chunk_id="chunk-1",
        report_id="report-1",
        text="Energy consumption is disclosed.",
        source_page=4,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(make_task(), [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.model_called is False
    assert result.assessment.evidence[0].source_page == 4
    assert result.recommendations == []


def test_disclosure_agent_marks_missing_evidence_for_manual_review_and_recommendation():
    result = DisclosureAgent().analyze(make_task(), [], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.recommendations[0].requirement_id == "GRI 302-1-a"


def test_disclosure_agent_uses_database_safe_recommendation_id_for_long_task_id():
    task = DisclosureTask(
        task_id="run-7170e39a373d48ad9d435912ae53bf0d:GRI 2-2-c-iii",
        run_id="run-7170e39a373d48ad9d435912ae53bf0d",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-2",
        requirement_id="GRI 2-2-c-iii",
        requirement_text="whether and how the approach differs across disclosures.",
        keywords=["approach", "differs", "disclosures"],
    )

    result = DisclosureAgent().analyze(task, [], confirm_llm=False)

    assert result.recommendations[0].recommendation_id.startswith("recommendation-")
    assert len(result.recommendations[0].recommendation_id) <= 64


def test_disclosure_agent_marks_2_2_a_boundary_only_evidence_as_partial():
    task = DisclosureTask(
        task_id="task-2-2-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-2",
        requirement_id="GRI 2-2-a",
        requirement_text="list all entities included in the organization's sustainability reporting.",
        keywords=["报告边界", "实际运营场所", "纳入报告"],
        candidate_pages=[3],
        candidate_page_source="report_gri_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-boundary",
        report_id="report-1",
        text="关于本报告：本报告边界覆盖远景能源所有实际运营场所，并纳入报告期内相关统计口径。",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "完整实体清单" in result.assessment.missing_items
    assert result.assessment.evidence[0].metadata["retrieval_strategy"] == "index_page_bounded"


def test_disclosure_agent_keeps_2_2_c_ii_fallback_only_evidence_unknown():
    task = DisclosureTask(
        task_id="task-2-2-c-ii",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-2",
        requirement_id="GRI 2-2-c-ii",
        requirement_text="explain the approach used for consolidating information, including mergers and acquisitions.",
        keywords=["并购", "收购", "处置"],
        candidate_pages=[3],
        candidate_page_source="report_gri_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-irrelevant",
        report_id="report-1",
        text="循环经济章节介绍风机产品循环利用，与并购、收购或实体处置口径无关。",
        source_page=26,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []
    assert result.recommendations[0].requirement_id == "GRI 2-2-c-ii"


def test_disclosure_agent_accepts_2_1_a_full_legal_name_on_supplemental_pages():
    task = DisclosureTask(
        task_id="task-2-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        requirement_text="report its legal name;",
        keywords=["有限公司", "Co., Ltd."],
        candidate_pages=[1, 3, 6],
        candidate_page_source="report_gri_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-cover",
        report_id="report-1",
        text="远景能源有限公司 Envision Energy Co., Ltd.",
        source_page=1,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
    assert result.recommendations == []


def test_disclosure_agent_rejects_2_1_b_company_name_as_legal_form():
    task = DisclosureTask(
        task_id="task-2-1-b",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-b",
        requirement_text="report its ownership and legal form;",
        keywords=["有限公司"],
        candidate_pages=[3],
        candidate_page_source="report_gri_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-name",
        report_id="report-1",
        text="报告主体为远景能源有限公司。",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "所有权性质" in result.assessment.missing_items
    assert "法律形式" in result.assessment.missing_items


def test_disclosure_agent_marks_2_1_c_headquarters_building_as_partial():
    task = DisclosureTask(
        task_id="task-2-1-c",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-c",
        requirement_text="report the location of its headquarters;",
        keywords=["总部", "上海总部", "总部大楼"],
        candidate_pages=[6, 28],
        candidate_page_source="report_gri_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-hq",
        report_id="report-1",
        text="上海总部大楼持续推进绿色运营。",
        source_page=28,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "正式总部所在地或地址" in result.assessment.missing_items


def test_disclosure_agent_marks_2_1_d_global_market_description_as_partial():
    task = DisclosureTask(
        task_id="task-2-1-d",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-d",
        requirement_text="report its countries of operation;",
        keywords=["全球", "海外订单", "全球项目", "亚太"],
        candidate_pages=[6],
        candidate_page_source="report_gri_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-operation",
        report_id="report-1",
        text="公司为全球领先企业，海外订单覆盖亚太及全球市场，参与多个全球项目。",
        source_page=6,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "运营国家清单" in result.assessment.missing_items


def test_disclosure_agent_marks_2_2_c_report_boundary_as_partial():
    task = DisclosureTask(
        task_id="task-2-2-c",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-2",
        requirement_id="GRI 2-2-c",
        requirement_text="explain the approach used for consolidating information.",
        keywords=["报告边界", "实际运营场所"],
        candidate_pages=[3],
        candidate_page_source="report_gri_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-boundary",
        report_id="report-1",
        text="报告边界包含远景能源所有实际运营场所。",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "多实体信息合并方法" in result.assessment.missing_items


def test_disclosure_agent_keeps_2_2_c_iii_boundary_only_evidence_unknown():
    task = DisclosureTask(
        task_id="task-2-2-c-iii",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-2",
        requirement_id="GRI 2-2-c-iii",
        requirement_text="whether and how the approach differs across disclosures.",
        keywords=["报告边界", "资料来源", "编制流程"],
        candidate_pages=[3],
        candidate_page_source="report_gri_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-about-report",
        report_id="report-1",
        text="关于本报告：本报告说明报告期、资料来源、编制流程和报告边界。",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "多实体信息合并方法" in result.assessment.missing_items
    assert "合并方法差异说明" in result.assessment.missing_items
    assert result.assessment.evidence == []
    assert result.recommendations[0].requirement_id == "GRI 2-2-c-iii"


def test_disclosure_agent_marks_2_3_a_reporting_period_as_partial():
    task = DisclosureTask(
        task_id="task-2-3-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-3",
        requirement_id="GRI 2-3-a",
        requirement_text="report the reporting period for, and the frequency of, its sustainability reporting.",
        keywords=["报告期", "报告频率"],
        candidate_pages=[3],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-period",
        report_id="report-1",
        text="本报告覆盖公司2024年1月1日至12月31日（以下简称“报告期”）期间的信息和数据。",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "报告频率" in result.assessment.missing_items


def test_disclosure_agent_accepts_2_3_d_contact_email():
    task = DisclosureTask(
        task_id="task-2-3-d",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-3",
        requirement_id="GRI 2-3-d",
        requirement_text="report the contact point for questions about the report or reported information.",
        keywords=["联系邮箱", "f_esg_office"],
        candidate_pages=[3],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-contact",
        report_id="report-1",
        text="获取及回应本报告 如有疑问，请通过 f_esg_office@envision-energy.com 联系。",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
    assert result.recommendations == []


def test_disclosure_agent_uses_no_restatement_index_note_for_2_4():
    for requirement_id in ["GRI 2-4-a", "GRI 2-4-a-i", "GRI 2-4-a-ii"]:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-4",
            requirement_id=requirement_id,
            requirement_text="report restatements of information.",
            keywords=["信息重述", "无信息重述"],
            candidate_pages=[71],
            candidate_page_source="gri_report_index",
            index_page=71,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text="GRI 指标索引 2-4 信息重述 无信息重述 /",
            source_page=71,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
        assert result.recommendations == []


def test_disclosure_agent_marks_2_5_a_assurance_page_as_partial():
    task = DisclosureTask(
        task_id="task-2-5-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-5",
        requirement_id="GRI 2-5-a",
        requirement_text="describe external assurance policy and practice.",
        keywords=["鉴证报告", "独立有限鉴证"],
        candidate_pages=[77],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-assurance",
        report_id="report-1",
        text="独立有限鉴证报告 远景能源ESG报告 2024",
        source_page=77,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "外部鉴证政策" in result.assessment.missing_items
    assert "治理机构和高管参与说明" in result.assessment.missing_items


def test_disclosure_agent_accepts_2_5_b_assurance_statement_reference():
    for requirement_id in ["GRI 2-5-b", "GRI 2-5-b-i"]:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-5",
            requirement_id=requirement_id,
            requirement_text="report external assurance details.",
            keywords=["鉴证报告", "独立有限鉴证"],
            candidate_pages=[77],
            candidate_page_source="gri_report_index",
            index_page=71,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text="独立有限鉴证报告 远景能源ESG报告 2024",
            source_page=77,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
        assert result.recommendations == []


def test_disclosure_agent_filters_new_global_fallback_false_hits():
    task = DisclosureTask(
        task_id="task-2-3-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-3",
        requirement_id="GRI 2-3-a",
        requirement_text="report the reporting period and frequency.",
        keywords=["报告期"],
        candidate_pages=[3],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-fallback",
        report_id="report-1",
        text="环境章节出现报告期字样，但不是关于本报告章节。",
        source_page=64,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []
