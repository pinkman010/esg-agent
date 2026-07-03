from src.agents.disclosure_agent import DisclosureAgent
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus
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


def test_disclosure_agent_accepts_2_5_b_ii_assurance_basis_with_ocr_flag():
    task = DisclosureTask(
        task_id="task-2-5-b-ii",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-5",
        requirement_id="GRI 2-5-b-ii",
        requirement_text="report the assurance standards and basis.",
        keywords=["鉴证报告", "鉴证标准"],
        candidate_pages=[77],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-assurance-basis",
        report_id="report-1",
        text="独立有限鉴证报告 远景能源ESG报告 2024",
        source_page=77,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
    assert result.assessment.evidence[0].requires_ocr is True
    assert result.assessment.evidence[0].needs_ocr_or_vlm is True


def test_disclosure_agent_marks_2_6_business_and_value_chain_evidence_as_partial():
    cases = [
        (
            "GRI 2-6-b",
            ["主要业务", "责任采购", "全球企业", "深化合作", "供应商准入", "供应商退出"],
            [
                (4, "全球企业 深化合作"),
                (6, "远景能源主要业务包括智能风电、智慧储能系统和绿氢解决方案。"),
                (52, "责任采购，产业共荣。远景能源致力于实施负责任、可持续的采购。"),
                (53, "供应商准入 尽职调查"),
                (54, "供应商退出 供应商培训 SMI CN100"),
            ],
            [4, 6, 52, 53, 54],
        ),
        (
            "GRI 2-6-b-i",
            ["主要业务", "智能风电", "智慧储能", "全球企业", "深化合作", "供应商退出"],
            [
                (4, "全球企业 深化合作"),
                (6, "远景能源主要业务包括智能风电、智慧储能系统和绿氢解决方案。"),
                (54, "供应商退出 供应商培训 SMI CN100"),
            ],
            [4, 6],
        ),
        (
            "GRI 2-6-b-ii",
            ["责任采购", "可持续供应链", "主要业务", "全球企业", "深化合作", "供应商准入", "供应商退出"],
            [
                (4, "全球企业 深化合作"),
                (6, "远景能源主要业务包括智能风电、智慧储能系统和绿氢解决方案。"),
                (52, "责任采购，产业共荣。远景能源致力于实施负责任、可持续的采购。"),
                (53, "供应商准入 尽职调查"),
                (54, "供应商退出 供应商培训 SMI CN100"),
            ],
            [52, 53, 54],
        ),
        (
            "GRI 2-6-c",
            ["business", "relationships", "ESG 合作网络", "价值链", "供应商大会", "全球企业", "深化合作", "SMI", "CN100"],
            [
                (4, "全球企业 深化合作"),
                (6, "business relationships generic company overview"),
                (9, "ESG 合作网络 UNGC RE100 SBTi CDP IEA WEF"),
                (52, "责任采购覆盖价值链合作伙伴。"),
                (53, "business relationships generic supplier process"),
                (54, "SMI CN100 供应商大会推动产业共荣。"),
            ],
            [4, 9, 52, 54],
        ),
    ]
    for requirement_id, keywords, page_texts, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-6",
            requirement_id=requirement_id,
            requirement_text="describe activities, value chain and business relationships.",
            keywords=keywords,
            candidate_pages=[4, 6, 9, 52, 53, 54],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=71,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{source_page}",
                report_id="report-1",
                text=text,
                source_page=source_page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for source_page, text in page_texts
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == expected_pages


def test_disclosure_agent_keeps_2_6_d_major_changes_unknown_and_filters_fallback():
    task = DisclosureTask(
        task_id="task-2-6-d",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-6",
        requirement_id="GRI 2-6-d",
        requirement_text="report significant changes compared to the previous reporting period.",
        keywords=["重大变化", "业务关系变化"],
        candidate_pages=[4, 6, 9, 52, 53, 54],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-invalid-fallback",
        report_id="report-1",
        text="温室气体核算方法说明中出现重大变化字样，但不涉及活动、价值链或业务关系变化。",
        source_page=64,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []


def test_disclosure_agent_marks_2_7_c_employee_compilation_context_as_partial():
    task = DisclosureTask(
        task_id="task-2-7-c",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-7",
        requirement_id="GRI 2-7-c",
        requirement_text="describe methodologies and assumptions used to compile employee data.",
        keywords=["截至报告期末", "员工组成", "人员结构"],
        candidate_pages=[33, 65],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-employee-structure",
        report_id="report-1",
        text="人员结构 截至报告期末，远景能源员工组成按性别、职级和年龄划分。",
        source_page=33,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "head count 或 FTE 口径" in result.assessment.missing_items


def test_disclosure_agent_accepts_2_7_c_ii_reporting_period_end_basis():
    task = DisclosureTask(
        task_id="task-2-7-c-ii",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-7",
        requirement_id="GRI 2-7-c-ii",
        requirement_text="whether employee numbers are reported at the end of the reporting period.",
        keywords=["截至报告期末", "员工组成"],
        candidate_pages=[33, 65],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-employee-period-end",
        report_id="report-1",
        text="人员结构 截至报告期末，远景能源员工组成按性别、职级和年龄划分。",
        source_page=33,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED


def test_disclosure_agent_marks_2_7_kpi_page_65_as_complex_table():
    task = DisclosureTask(
        task_id="task-2-7-c",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-7",
        requirement_id="GRI 2-7-c",
        requirement_text="describe methodologies and assumptions used to compile employee data.",
        keywords=["员工组成", "社会绩效"],
        candidate_pages=[33, 65],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-employee-kpi-table",
        report_id="report-1",
        text="社会绩效 员工组成 2024 2023 2022 男性 女性 新进员工 离职员工 员工流失率",
        source_page=65,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.evidence[0].source_page == 65
    assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[0].quality_flags


def test_disclosure_agent_keeps_2_7_e_unknown_without_employee_fluctuation_evidence():
    task = DisclosureTask(
        task_id="task-2-7-e",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-7",
        requirement_id="GRI 2-7-e",
        requirement_text="report significant fluctuations in employee numbers during or between reporting periods.",
        keywords=["重大波动", "员工人数变化", "员工流失率"],
        candidate_pages=[33, 65],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-employee-kpi",
        report_id="report-1",
        text="社会绩效 员工组成 2024 2023 2022 新进员工 离职员工 员工流失率",
        source_page=65,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []


def test_disclosure_agent_keeps_2_8_non_employee_worker_items_unknown_and_filters_fallback():
    task = DisclosureTask(
        task_id="task-2-8-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-8",
        requirement_id="GRI 2-8-a",
        requirement_text="report workers who are not employees.",
        keywords=["非雇员工作者", "承包商", "供应商"],
        candidate_pages=[52, 63, 71],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-ordinary-employee",
        report_id="report-1",
        text="普通员工关怀、供应商管理和承包商安全内容不能替代非雇员工作者数量披露。",
        source_page=32,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []


def test_disclosure_agent_marks_2_9_b_esg_governance_architecture_as_partial():
    task = DisclosureTask(
        task_id="task-2-9-b",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-9",
        requirement_id="GRI 2-9-b",
        requirement_text="list committees of the highest governance body responsible for decision-making on impacts.",
        keywords=["ESG治理架构", "ESG委员会", "ESG办公室", "ESG议题执行小组"],
        candidate_pages=[13],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-esg-governance",
        report_id="report-1",
        text="ESG治理架构 ESG委员会为公司ESG最高决策机构，ESG办公室是ESG常设管理机构，ESG议题执行小组为ESG战略执行层。",
        source_page=13,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "最高治理机构委员会体系" in result.assessment.missing_items


def test_disclosure_agent_marks_allowed_governance_impact_items_as_partial():
    allowed_requirement_ids = [
        "GRI 2-9-a",
        "GRI 2-9-b",
        "GRI 2-12-a",
        "GRI 2-12-b",
        "GRI 2-12-b-i",
        "GRI 2-12-b-ii",
        "GRI 2-12-c",
        "GRI 2-13-a",
        "GRI 2-13-a-i",
        "GRI 2-13-a-ii",
        "GRI 2-13-b",
    ]
    chunk = DocumentChunk(
        chunk_id="chunk-governance-architecture",
        report_id="report-1",
        text=(
            "ESG治理架构 ESG委员会为公司ESG最高决策机构，由CEO任主席，成员包括CPO、CFO、COO、CSO。"
            "ESG办公室由CSO直接领导，向ESG委员会季度汇报，ESG议题执行小组月度拉通。"
        ),
        source_page=13,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    for requirement_id in allowed_requirement_ids:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="-".join(requirement_id.split("-")[:2]),
            requirement_id=requirement_id,
            requirement_text="describe governance roles for impact management.",
            keywords=["ESG治理架构", "ESG委员会", "ESG办公室", "季度汇报"],
            candidate_pages=[13],
            candidate_page_source="gri_report_index",
            index_page=71,
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == [13]


def test_disclosure_agent_does_not_use_governance_architecture_for_forbidden_governance_items():
    forbidden_requirement_ids = ["GRI 2-9-c", "GRI 2-9-c-i", "GRI 2-11-a", "GRI 2-11-b"]
    chunk = DocumentChunk(
        chunk_id="chunk-governance-architecture",
        report_id="report-1",
        text="ESG治理架构 ESG委员会由CEO任主席，成员包括CPO、CFO、COO、CSO。",
        source_page=13,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    for requirement_id in forbidden_requirement_ids:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="-".join(requirement_id.split("-")[:2]),
            requirement_id=requirement_id,
            requirement_text="report complete governance composition or chair details.",
            keywords=["ESG治理架构", "ESG委员会", "CEO"],
            candidate_pages=[13],
            candidate_page_source="gri_report_index",
            index_page=71,
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []


def test_disclosure_agent_keeps_omission_note_evidence_without_upgrading_verdict():
    for requirement_id in ["GRI 2-10-a", "GRI 2-19-a", "GRI 2-20-a"]:
        disclosure_id = "-".join(requirement_id.split("-")[:2])
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="omitted disclosure due to confidentiality.",
            keywords=["从略披露", "因商业保密限制从略披露"],
            candidate_pages=[71],
            candidate_page_source="gri_report_index_omission_note",
            index_page=71,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-omission-{requirement_id}",
            report_id="report-1",
            text=f"{disclosure_id.removeprefix('GRI ')} 因商业保密限制从略披露 /",
            source_page=71,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence[0].source_page == 71
        assert result.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
        assert disclosure_id.removeprefix("GRI ") in result.assessment.evidence[0].evidence_preview


def test_disclosure_agent_marks_omission_note_only_for_target_index_row():
    index_text = (
        "2-4 信息重述 无信息重述 /\n"
        "2-10 最高管治机构的提名和遴选 因商业保密限制从略披露 /\n"
        "2-20 确定薪酬的程序 因商业保密限制从略披露 / 2-21 年度总薪酬比率 因商业保密限制从略披露 /"
    )
    restatement_task = DisclosureTask(
        task_id="task-2-4-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-4",
        requirement_id="GRI 2-4-a",
        requirement_text="report restatements of information.",
        keywords=["信息重述", "无信息重述"],
        candidate_pages=[71],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    remuneration_task = DisclosureTask(
        task_id="task-2-20-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-20",
        requirement_id="GRI 2-20-a",
        requirement_text="describe process to determine remuneration.",
        keywords=["从略披露", "因商业保密限制从略披露"],
        candidate_pages=[71],
        candidate_page_source="gri_report_index_omission_note",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-index",
        report_id="report-1",
        text=index_text,
        source_page=71,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    restatement = DisclosureAgent().analyze(restatement_task, [chunk], confirm_llm=False)
    remuneration = DisclosureAgent().analyze(remuneration_task, [chunk], confirm_llm=False)

    assert restatement.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert restatement.assessment.evidence[0].metadata.get("evidence_type") is None
    assert remuneration.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert remuneration.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
    assert "2-20 确定薪酬的程序 因商业保密限制从略披露 /" in remuneration.assessment.evidence[0].evidence_preview
    assert "2-21" not in remuneration.assessment.evidence[0].evidence_preview


def test_disclosure_agent_clears_global_fallback_for_omitted_remuneration_process():
    task = DisclosureTask(
        task_id="task-2-20-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-20",
        requirement_id="GRI 2-20-a",
        requirement_text="describe process to determine remuneration.",
        keywords=["薪酬", "流程"],
        candidate_pages=[71],
        candidate_page_source="gri_report_index_omission_note",
        index_page=71,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-wrong-employee-page",
        report_id="report-1",
        text="挑战者代表聚焦流程与人，帮助公司人才进化。",
        source_page=33,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []
