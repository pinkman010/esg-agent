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


def test_disclosure_agent_propagates_new_omission_notes_for_current_150():
    cases = [
        ("GRI 2-20-a-iii", "GRI 2-20", "2-20 确定薪酬的程序 因商业保密限制从略披露 /", 71),
        ("GRI 2-20-b", "GRI 2-20", "2-20 确定薪酬的程序 因商业保密限制从略披露 /", 71),
        ("GRI 2-21-a", "GRI 2-21", "2-21 年度总薪酬比率 因商业保密限制从略披露 /", 71),
        ("GRI 2-21-b", "GRI 2-21", "2-21 年度总薪酬比率 因商业保密限制从略披露 /", 71),
        ("GRI 2-21-c", "GRI 2-21", "2-21 年度总薪酬比率 因商业保密限制从略披露 /", 71),
        ("GRI 2-30-a", "GRI 2-30", "2-30 集体谈判协议 因商业保密限制从略披露 /", 72),
        ("GRI 2-30-b", "GRI 2-30", "2-30 集体谈判协议 因商业保密限制从略披露 /", 72),
    ]
    for requirement_id, disclosure_id, text, source_page in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2021",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="omitted disclosure due to confidentiality.",
            keywords=["从略披露", "因商业保密限制从略披露"],
            candidate_pages=[source_page],
            candidate_page_source="gri_report_index_omission_note",
            index_page=source_page,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text=text,
            source_page=source_page,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
        assert result.assessment.evidence[0].metadata["omission_reason"] == "confidentiality"


def test_disclosure_agent_marks_current_150_policy_items_as_partial():
    cases = [
        ("GRI 2-22-a", "GRI 2-22", [(4, "董事长致辞 可持续发展 零碳目标"), (5, "CSO 致辞 可持续发展")], [4, 5]),
        ("GRI 2-23-a", "GRI 2-23", [(9, "UNGC 世界人权宣言"), (11, "政策承诺"), (32, "劳工与人权 ILO"), (54, "供应商行为准则"), (57, "合规制度"), (59, "举报机制")], [9, 11, 32, 54, 57, 59]),
        ("GRI 2-23-a-i", "GRI 2-23", [(9, "UNGC 十项原则"), (32, "ILO 世界人权宣言")], [9, 32]),
        ("GRI 2-23-a-ii", "GRI 2-23", [(53, "供应商尽调"), (58, "第三方反腐败尽调")], [53, 58]),
        ("GRI 2-23-a-iv", "GRI 2-23", [(32, "劳工与人权保护政策"), (54, "供应商行为准则 员工人权")], [32, 54]),
        ("GRI 2-23-b", "GRI 2-23", [(9, "UNGC"), (32, "世界人权宣言"), (54, "供应商员工人权")], [9, 32, 54]),
        ("GRI 2-23-e", "GRI 2-23", [(32, "员工政策 运营环节"), (54, "供应商行为准则 供应商网络")], [32, 54]),
        ("GRI 2-23-f", "GRI 2-23", [(32, "人权培训"), (54, "供应商培训与赋能"), (59, "合规文化培训")], [32, 54, 59]),
        ("GRI 2-24-a", "GRI 2-24", [(11, "ESG战略 政策承诺"), (13, "ESG治理架构"), (32, "员工人权政策"), (53, "供应商风险管理"), (54, "供应商行为准则"), (57, "合规制度"), (59, "培训")], [11, 13, 32, 53, 54, 57, 59]),
        ("GRI 2-25-a", "GRI 2-25", [(32, "人权侵害投诉机制"), (53, "供应商整改退出闭环"), (59, "举报调查处理机制")], [32, 53, 59]),
        ("GRI 2-25-b", "GRI 2-25", [(32, "投诉机制"), (59, "阳光热线 举报电话 举报邮箱 地址")], [32, 59]),
        ("GRI 2-25-c", "GRI 2-25", [(53, "供应商整改闭环"), (57, "合规风险排查"), (59, "举报调查处理")], [53, 57, 59]),
        ("GRI 2-25-e", "GRI 2-25", [(56, "投诉处理率"), (58, "舞弊案件调查完结率"), (59, "整改闭环率")], [56, 58, 59]),
        ("GRI 2-28-a", "GRI 2-28", [(9, "UNGC RE100 SBTi CDP IEA WEF")], [9]),
        ("GRI 2-29-a", "GRI 2-29", [(14, "利益相关方沟通 关注议题 沟通渠道"), (15, "重要性评估")], [14, 15]),
        ("GRI 3-1-a", "GRI 3-1", [(14, "利益相关方沟通"), (15, "重要性评估 重要性矩阵 问卷 部门访谈")], [14, 15]),
    ]
    for requirement_id, disclosure_id, page_texts, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2021",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="policy or stakeholder disclosure.",
            keywords=["政策承诺", "人权", "供应商", "阳光热线", "UNGC", "利益相关方", "重要性评估"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=72,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{page}",
                report_id="report-1",
                text=text,
                source_page=page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for page, text in page_texts
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == expected_pages


def test_disclosure_agent_keeps_current_150_unknown_items_without_evidence():
    cases = [
        ("GRI 2-23-a-iii", "GRI 2-23", "预防原则"),
        ("GRI 2-23-c", "GRI 2-23", "政策链接"),
        ("GRI 2-23-d", "GRI 2-23", "审批层级"),
        ("GRI 2-25-d", "GRI 2-25", "使用者参与机制设计"),
        ("GRI 2-26-a-i", "GRI 2-26", "寻求建议"),
        ("GRI 2-27-d", "GRI 2-27", "重大违法违规界定"),
    ]
    for requirement_id, disclosure_id, text in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2021",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="missing current 150 detail.",
            keywords=[text],
            candidate_pages=[9, 32, 53, 59, 72],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=72,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text=text,
            source_page=59,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []


def test_disclosure_agent_handles_2_26_and_2_27_specific_rules():
    cases = [
        ("GRI 2-26-a", "GRI 2-26", [(33, "挑战者代表 建言献策"), (59, "阳光热线 举报电话 举报邮箱")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [33, 59], "substantive"),
        ("GRI 2-26-a-ii", "GRI 2-26", [(59, "阳光热线 举报电话 举报邮箱 鼓励报告疑似违规 腐败 不当行为 举报人保护")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [59], "substantive"),
        ("GRI 2-27-a", "GRI 2-27", [(72, "2-27 遵守法律法规 报告期内未发生违法违规事件 /")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [72], "index_statement"),
        ("GRI 2-27-a-i", "GRI 2-27", [(72, "2-27 遵守法律法规 报告期内未发生违法违规事件 /")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [72], "index_statement"),
    ]
    for requirement_id, disclosure_id, page_texts, verdict, review_status, expected_pages, evidence_type in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2021",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="specific current 150 rule.",
            keywords=["阳光热线", "举报", "未发生违法违规事件"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=72,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{page}",
                report_id="report-1",
                text=text,
                source_page=page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for page, text in page_texts
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is verdict
        assert result.assessment.review_status is review_status
        assert [item.source_page for item in result.assessment.evidence] == expected_pages
        assert result.assessment.evidence[0].metadata.get("evidence_type", "substantive") == evidence_type


def test_disclosure_agent_propagates_topic_specific_omission_notes_for_current_200():
    cases = [
        ("GRI 201-1-a", "GRI 201-1", "201-1 直接产生和分配的经济价值 因商业保密限制从略披露 /"),
        ("GRI 201-1-a-i", "GRI 201-1", "201-1 直接产生和分配的经济价值 因商业保密限制从略披露 /"),
        ("GRI 201-1-a-ii", "GRI 201-1", "201-1 直接产生和分配的经济价值 因商业保密限制从略披露 /"),
        ("GRI 201-1-a-iii", "GRI 201-1", "201-1 直接产生和分配的经济价值 因商业保密限制从略披露 /"),
        ("GRI 201-1-b", "GRI 201-1", "201-1 直接产生和分配的经济价值 因商业保密限制从略披露 /"),
        ("GRI 201-4-a", "GRI 201-4", "201-4 政府给予的财政补贴 因商业保密限制从略披露 /"),
        ("GRI 201-4-a-viii", "GRI 201-4", "201-4 政府给予的财政补贴 因商业保密限制从略披露 /"),
        ("GRI 201-4-c", "GRI 201-4", "201-4 政府给予的财政补贴 因商业保密限制从略披露 /"),
        ("GRI 202-2-a", "GRI 202-2", "202-2 从当地社区雇用高管的比例 因商业保密限制从略披露 /"),
        ("GRI 202-2-d", "GRI 202-2", "202-2 从当地社区雇用高管的比例 因商业保密限制从略披露 /"),
    ]
    for requirement_id, disclosure_id, text in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="topic-specific omitted disclosure due to confidentiality.",
            keywords=["从略披露", "因商业保密限制从略披露"],
            candidate_pages=[72],
            candidate_page_source="gri_report_index_omission_note",
            index_page=72,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text=text,
            source_page=72,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
        assert result.assessment.evidence[0].metadata["omission_reason"] == "confidentiality"


def test_disclosure_agent_rejects_201_3_employee_welfare_as_retirement_plan_evidence():
    task = DisclosureTask(
        task_id="task-201-3-d",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 201",
        standard_version="2016",
        disclosure_id="GRI 201-3",
        requirement_id="GRI 201-3-d",
        requirement_text="employee and employer contribution percentages.",
        keywords=["员工", "福利", "缴费"],
        candidate_pages=[32, 34],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=72,
    )
    chunks = [
        DocumentChunk(
            chunk_id="chunk-201-3-32",
            report_id="report-1",
            text="关怀员工 幸福职场 员工权益 人权 DEI 最佳雇主。",
            source_page=32,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-201-3-34",
            report_id="report-1",
            text="薪酬福利 社会保障 医疗保险 补充住房公积金 补充商业医疗。",
            source_page=34,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []


def test_disclosure_agent_handles_201_2_climate_financial_implication_rules():
    cases = [
        ("GRI 201-2-a", AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [17, 18, 19]),
        ("GRI 201-2-a-i", AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [17, 18]),
        ("GRI 201-2-a-ii", AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [17, 18]),
        ("GRI 201-2-a-iii", AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [17, 18]),
        ("GRI 201-2-a-iv", AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [17, 18, 19]),
    ]
    page_texts = {
        17: "气候风险 急性实体风险 慢性实体风险 科技风险 法律风险 市场风险 声誉风险 维修成本上升 订单损失。",
        18: "气候机遇 市场 产品与服务 能源来源 资源效率 韧性 绿色投融资 低成本资金 新能源政策激励。",
        19: "气候风险管理流程 识别 分析 管理 按月 季度 半年审查 应对措施。",
    }
    for requirement_id, verdict, review_status, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 201",
            standard_version="2016",
            disclosure_id="GRI 201-2",
            requirement_id=requirement_id,
            requirement_text="climate-related risks and opportunities financial implications.",
            keywords=["气候风险", "气候机遇", "财务影响", "应对措施", "风险管理流程"],
            candidate_pages=[17, 18, 19],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=72,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{page}",
                report_id="report-1",
                text=page_texts[page],
                source_page=page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for page in [17, 18, 19]
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is verdict
        assert result.assessment.review_status is review_status
        assert [item.source_page for item in result.assessment.evidence] == expected_pages


def test_disclosure_agent_keeps_201_2_action_cost_unknown_without_cost_evidence():
    task = DisclosureTask(
        task_id="task-201-2-a-v",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 201",
        standard_version="2016",
        disclosure_id="GRI 201-2",
        requirement_id="GRI 201-2-a-v",
        requirement_text="costs of actions taken to manage climate-related risks and opportunities.",
        keywords=["应对措施", "绿色债券", "成本"],
        candidate_pages=[17, 18, 19],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=72,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-201-2-a-v",
        report_id="report-1",
        text="应对措施 绿色债券 SLL 节能改造 低碳技术。",
        source_page=19,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []


def test_disclosure_agent_handles_203_indirect_economic_impact_rules():
    cases = [
        ("GRI 203-1-a", "GRI 203-1", [42, 43, 44]),
        ("GRI 203-1-b", "GRI 203-1", [4, 42, 43, 44]),
        ("GRI 203-1-c", "GRI 203-1", [42, 43, 44]),
        ("GRI 203-2-a", "GRI 203-2", [4, 12, 42, 43, 44]),
        ("GRI 203-2-b", "GRI 203-2", [12, 42, 43, 44, 69]),
    ]
    page_texts = {
        4: "董事长致辞 绿色能源项目 产业升级 当地经济。",
        12: "UN SDGs 千乡万村驭风行动 乡村振兴 一带一路。",
        42: "携手社区 贡献社会 乡村振兴工程。",
        43: "沙特风电装备合资公司 国际可持续对话 印度森林保护 老挝项目捐赠。",
        44: "清华可持续基金 西藏地震援助 社区公益。",
        69: "UN SDGs 乡村振兴 一带一路 G20 可持续发展论坛。",
    }
    for requirement_id, disclosure_id, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 203",
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="infrastructure investments, supported services, and indirect economic impacts.",
            keywords=["携手社区", "乡村振兴", "SDGs", "间接经济影响"],
            candidate_pages=expected_pages,
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=72,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{page}",
                report_id="report-1",
                text=page_texts[page],
                source_page=page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for page in expected_pages
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == expected_pages


def test_disclosure_agent_propagates_204_1_omission_note_for_current_250():
    for requirement_id in ["GRI 204-1-a", "GRI 204-1-b", "GRI 204-1-c"]:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 204",
            standard_version="2016",
            disclosure_id="GRI 204-1",
            requirement_id=requirement_id,
            requirement_text="proportion of spending on local suppliers.",
            keywords=["从略披露", "因商业保密限制从略披露"],
            candidate_pages=[73],
            candidate_page_source="gri_report_index_omission_note",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text="204-1 向当地供应商采购的支出比例 因商业保密限制从略披露 /",
            source_page=73,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
        assert result.assessment.evidence[0].metadata["omission_reason"] == "confidentiality"


def test_disclosure_agent_handles_205_anti_corruption_partial_and_disclosed_rules():
    cases = [
        ("GRI 205-1-a", "GRI 205-1", [(58, "贪污贿赂风险评估 内部和外部商业道德审计 识别高风险环节"), (68, "完成商业道德问题和腐败相关内部审计或风险评估的经营地点占比")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [58, 68]),
        ("GRI 205-1-b", "GRI 205-1", [(58, "关键业务流程分析 识别高风险环节 员工行为规范 廉洁风险")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [58]),
        ("GRI 205-2-b", "GRI 205-2", [(59, "全体员工年度合规申报 合规培训 利益冲突申报 纪律合规文化月"), (68, "反腐败和贿赂培训次数 累计小时数")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [59, 68]),
        ("GRI 205-2-c", "GRI 205-2", [(54, "目标供应商100%签署可持续采购章程 供应商行为准则"), (58, "所有供应商均已签署供应商阳光协议 第三方合作伙伴反腐败尽职调查")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [54, 58]),
        ("GRI 205-2-e", "GRI 205-2", [(59, "员工合规培训 纪律合规文化月"), (68, "反腐败和贿赂培训次数 累计小时数")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [59, 68]),
        ("GRI 205-3-a", "GRI 205-3", [(58, "舞弊案件调查完结率 商业道德管理"), (68, "贪污腐败事件数量")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [58, 68]),
        ("GRI 205-3-b", "GRI 205-3", [(68, "员工因腐败被开除或受到处分的事件数量")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [68]),
        ("GRI 206-1-a", "GRI 206-1", [(68, "反竞争行为事件数量")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [68]),
    ]
    for requirement_id, disclosure_id, page_texts, verdict, review_status, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="anti-corruption or anti-competitive topic-specific disclosure.",
            keywords=["反腐败", "贪污腐败", "商业道德", "风险评估", "合规培训", "供应商阳光协议", "反竞争行为"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{page}",
                report_id="report-1",
                text=text,
                source_page=page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for page, text in page_texts
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is verdict
        assert result.assessment.review_status is review_status
        assert [item.source_page for item in result.assessment.evidence] == expected_pages


def test_disclosure_agent_keeps_205_206_unreported_subitems_unknown():
    cases = [
        ("GRI 205-2-a", "GRI 205-2", "治理机构成员 反腐败政策传达"),
        ("GRI 205-2-d", "GRI 205-2", "治理机构成员 反腐败培训"),
        ("GRI 205-3-c", "GRI 205-3", "供应商退出 合同终止"),
        ("GRI 205-3-d", "GRI 205-3", "公开法律案件 腐败"),
        ("GRI 206-1-b", "GRI 206-1", "法律行动结果 判决"),
    ]
    for requirement_id, disclosure_id, text in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="unreported anti-corruption or anti-competitive subitem.",
            keywords=[text],
            candidate_pages=[54, 58, 59, 68],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text=text,
            source_page=68,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []


def test_disclosure_agent_propagates_207_4_omission_note_for_current_250():
    cases = [
        "GRI 207-4-a",
        "GRI 207-4-b",
        "GRI 207-4-b-i",
        "GRI 207-4-b-ii",
        "GRI 207-4-b-iii",
        "GRI 207-4-b-iv",
        "GRI 207-4-b-v",
        "GRI 207-4-b-vi",
        "GRI 207-4-b-vii",
        "GRI 207-4-b-viii",
        "GRI 207-4-b-ix",
        "GRI 207-4-b-x",
        "GRI 207-4-c",
    ]
    for requirement_id in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 207",
            standard_version="2019",
            disclosure_id="GRI 207-4",
            requirement_id=requirement_id,
            requirement_text="country-by-country reporting omitted due to confidentiality.",
            keywords=["从略披露", "因商业保密限制从略披露"],
            candidate_pages=[73],
            candidate_page_source="gri_report_index_omission_note",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text="207-4 国别报告 因商业保密限制从略披露 /",
            source_page=73,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
        assert result.assessment.evidence[0].metadata["omission_reason"] == "confidentiality"


def test_disclosure_agent_handles_207_tax_governance_partial_rules():
    cases = [
        "GRI 207-1-a",
        "GRI 207-1-a-iii",
        "GRI 207-2-a",
        "GRI 207-2-a-i",
        "GRI 207-2-a-ii",
        "GRI 207-2-a-iii",
        "GRI 207-2-a-iv",
        "GRI 207-3-a",
    ]
    for requirement_id in cases:
        disclosure_id = "GRI 207-3" if requirement_id.startswith("GRI 207-3") else ("GRI 207-2" if requirement_id.startswith("GRI 207-2") else "GRI 207-1")
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 207",
            standard_version="2019",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="tax approach governance control risk management or stakeholder concerns.",
            keywords=["税务治理", "财务合规", "税务管理标准", "税法要求", "利益相关方"],
            candidate_pages=[57],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}-57",
            report_id="report-1",
            text="严格按照国内外财务法律法规及税收协定开展经营，设立财务合规与安全部门负责税务治理和财务风险管理，制定规范文件和税务管理标准，持续追踪运营所在地税法要求与风险演变，深入掌握利益相关方对税务管理的期待。",
            source_page=57,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == [57]


def test_disclosure_agent_keeps_207_3_subitems_unknown_without_full_stakeholder_tax_process():
    for requirement_id in ["GRI 207-3-a-i", "GRI 207-3-a-ii", "GRI 207-3-a-iii"]:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 207",
            standard_version="2019",
            disclosure_id="GRI 207-3",
            requirement_id=requirement_id,
            requirement_text="tax authority engagement, public policy advocacy, or stakeholder tax concern process.",
            keywords=["税务机关沟通", "公共政策倡导", "外部利益相关方意见"],
            candidate_pages=[57],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}-57",
            report_id="report-1",
            text="深入掌握利益相关方对税务管理的期待。",
            source_page=57,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []


def test_disclosure_agent_handles_302_1_energy_kpi_partial_rules():
    cases = [
        ("GRI 302-1-a", "不可再生能源燃料消耗量 汽油 柴油 天然气 电力 热力 液化石油气 不可再生能源消耗总量(kWh)"),
        ("GRI 302-1-c", "电力消耗总量(kWh) 办公用电总量(kWh) 绿色电力使用总量(kWh)"),
    ]
    for requirement_id, text in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 302",
            standard_version="2016",
            disclosure_id="GRI 302-1",
            requirement_id=requirement_id,
            requirement_text="energy consumption within the organization.",
            keywords=["不可再生能源", "电力消耗", "能源消耗"],
            candidate_pages=[63],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}-63",
            report_id="report-1",
            text=text,
            source_page=63,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == [63]
        assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[0].quality_flags


def test_disclosure_agent_keeps_unreported_302_1_energy_subitems_unknown():
    for requirement_id in ["GRI 302-1-b", "GRI 302-1-d"]:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 302",
            standard_version="2016",
            disclosure_id="GRI 302-1",
            requirement_id=requirement_id,
            requirement_text="renewable fuel or sold energy consumption.",
            keywords=["可再生燃料消耗", "售出的电力"],
            candidate_pages=[63],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}-63",
            report_id="report-1",
            text="绿色电力使用总量(kWh) 电力消耗总量(kWh)",
            source_page=63,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []


def test_disclosure_agent_handles_302_1_total_energy_disclosed_rule():
    task = DisclosureTask(
        task_id="task-302-1-e",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 302",
        standard_version="2016",
        disclosure_id="GRI 302-1",
        requirement_id="GRI 302-1-e",
        requirement_text="total energy consumption inside the organization.",
        keywords=["能源使用总量", "总能耗"],
        candidate_pages=[63],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=73,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-302-1-e-63",
        report_id="report-1",
        text="能源使用总量 177,478,406.50 kWh",
        source_page=63,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
    assert [item.source_page for item in result.assessment.evidence] == [63]
    assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[0].quality_flags


def test_disclosure_agent_handles_302_4_energy_reduction_partial_rules():
    cases = [
        ("GRI 302-4-a", [23, 63]),
        ("GRI 302-4-b", [23, 63]),
    ]
    page_texts = {
        23: "节能改造 年节约用电约 9,360 kWh。",
        63: "节能措施促成节电量 292,106 kWh。",
    }
    for requirement_id, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 302",
            standard_version="2016",
            disclosure_id="GRI 302-4",
            requirement_id=requirement_id,
            requirement_text="reductions in energy consumption.",
            keywords=["节能改造", "节电量", "减少能源消耗"],
            candidate_pages=expected_pages,
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{page}",
                report_id="report-1",
                text=page_texts[page],
                source_page=page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for page in expected_pages
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == expected_pages


def test_disclosure_agent_keeps_unreported_302_4_and_302_5_unknown():
    cases = ["GRI 302-4-c", "GRI 302-4-d", "GRI 302-5-a", "GRI 302-5-b", "GRI 302-5-c"]
    for requirement_id in cases:
        disclosure_id = "GRI 302-5" if requirement_id.startswith("GRI 302-5") else "GRI 302-4"
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 302",
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="energy reduction basis or product energy requirements.",
            keywords=["基准", "方法", "售出产品"],
            candidate_pages=[23, 63],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text="节能改造 节能措施促成节电量。",
            source_page=63,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []


def test_disclosure_agent_handles_303_water_management_and_accounting_partial_rules():
    cases = [
        ("GRI 303-1-a", "GRI 303-1", [(25, "水资源使用 风险评估 取水 排水 耗水"), (63, "水资源 KPI 总取水量 总排水量")]),
        ("GRI 303-1-b", "GRI 303-1", [(25, "WWF Water Risk Filter 水资源风险评估")]),
        ("GRI 303-1-c", "GRI 303-1", [(22, "废水分类处理 回用"), (25, "节水 循环水 雨水替代 逆流清洗")]),
        ("GRI 303-1-d", "GRI 303-1", [(16, "水资源目标 行动路径"), (25, "水资源管理目标")]),
        ("GRI 303-2-a", "GRI 303-2", [(22, "废水分类收集 分质处理 排放水质达到或优于法规限值")]),
        ("GRI 303-2-a-ii", "GRI 303-2", [(22, "水资源管控标准"), (25, "水资源管理标准和政策")]),
        ("GRI 303-3-a", "GRI 303-3", [(25, "高风险区域运营地点和取水占比"), (63, "总取水量 地表水总量 地下水总量 第三方取水总量")]),
        ("GRI 303-3-a-i", "GRI 303-3", [(63, "地表水总量")]),
        ("GRI 303-3-a-ii", "GRI 303-3", [(63, "地下水总量")]),
        ("GRI 303-3-a-v", "GRI 303-3", [(63, "第三方取水总量")]),
        ("GRI 303-3-b", "GRI 303-3", [(25, "高风险区域运营地点和取水占比"), (63, "高水风险区域取水")]),
        ("GRI 303-3-c", "GRI 303-3", [(63, "第三方淡水总量 第三方其他水总量")]),
        ("GRI 303-3-c-i", "GRI 303-3", [(63, "第三方淡水总量")]),
        ("GRI 303-3-c-ii", "GRI 303-3", [(63, "第三方其他水总量")]),
        ("GRI 303-4-a", "GRI 303-4", [(22, "废水分类处理"), (63, "总排水量")]),
        ("GRI 303-4-b", "GRI 303-4", [(63, "淡水排水量 其他水排水量")]),
        ("GRI 303-4-b-i", "GRI 303-4", [(63, "淡水排水量")]),
        ("GRI 303-4-b-ii", "GRI 303-4", [(63, "其他水排水量")]),
    ]
    for requirement_id, disclosure_id, page_texts in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 303",
            standard_version="2018",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="water management, withdrawal, or discharge disclosure.",
            keywords=["水资源", "取水", "排水", "废水", "淡水", "第三方"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-{page}",
                report_id="report-1",
                text=text,
                source_page=page,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
            for page, text in page_texts
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == [page for page, _ in page_texts]


def test_disclosure_agent_keeps_unreported_303_water_subitems_unknown():
    cases = [
        "GRI 303-2-a-i",
        "GRI 303-2-a-iii",
        "GRI 303-2-a-iv",
        "GRI 303-3-a-iii",
        "GRI 303-3-a-iv",
        "GRI 303-3-b-i",
        "GRI 303-3-b-ii",
        "GRI 303-3-b-iii",
        "GRI 303-3-b-iv",
        "GRI 303-3-b-v",
        "GRI 303-3-d",
        "GRI 303-4-a-i",
        "GRI 303-4-a-ii",
        "GRI 303-4-a-iii",
        "GRI 303-4-a-iv",
    ]
    for requirement_id in cases:
        disclosure_id = "GRI 303-2" if requirement_id.startswith("GRI 303-2") else ("GRI 303-4" if requirement_id.startswith("GRI 303-4") else "GRI 303-3")
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 303",
            standard_version="2018",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="unreported water disclosure subitem.",
            keywords=["海水", "采出水", "受纳水体", "地表水排放"],
            candidate_pages=[22, 25, 63],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=73,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text="水资源管理 取水 排水 KPI。",
            source_page=63,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []
