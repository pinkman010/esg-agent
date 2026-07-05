from src.agents.disclosure_agent import DisclosureAgent
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus
from src.domain.models import DisclosureTask, DocumentChunk
from src.standards.evidence_contracts import RequirementEvidenceContract
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup


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


def test_disclosure_agent_applies_ontology_matrix_before_generic_disclosed(monkeypatch):
    def fake_contract(requirement_id):
        if requirement_id != "GRI TEST-1-a":
            return None
        return RequirementEvidenceContract(
            requirement_id=requirement_id,
            allowed_pages=(4,),
            candidate_pages=(4,),
            facets=(
                RequirementFacet.REQUIRES_GENDER_BREAKDOWN,
                RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN,
            ),
            evidence_kinds=(EvidenceKind.KPI_VALUE,),
            semantic_group=SemanticGroup.BREAKDOWN_DIMENSION,
        )

    monkeypatch.setattr("src.agents.disclosure_agent.get_requirement_contract", fake_contract)
    task = DisclosureTask(
        task_id="task-ontology",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI TEST",
        requirement_id="GRI TEST-1-a",
        requirement_text="Disclose average hours by gender and employee category.",
        keywords=["training"],
        candidate_pages=[4],
        candidate_page_source="contract_candidate",
    )
    chunk = DocumentChunk(
        chunk_id="chunk-ontology",
        report_id="report-1",
        text="The report discloses total training hours and average training hours per employee.",
        source_page=4,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "按性别拆分" in result.assessment.missing_items
    assert "按员工类别拆分" in result.assessment.missing_items
    assert result.assessment.evidence[0].metadata["decision_source"] == "ontology_matrix"


def test_disclosure_agent_merges_contract_missing_items_with_ontology_result(monkeypatch):
    def fake_contract(requirement_id):
        if requirement_id != "GRI TEST-supplier-termination":
            return None
        return RequirementEvidenceContract(
            requirement_id=requirement_id,
            allowed_pages=(67,),
            candidate_pages=(67,),
            kpi_table_pages=(67,),
            facets=(RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY),
            evidence_kinds=(EvidenceKind.KPI_VALUE,),
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            missing_items=("终止关系百分比", "终止关系原因说明"),
        )

    monkeypatch.setattr("src.agents.disclosure_agent.get_requirement_contract", fake_contract)
    task = DisclosureTask(
        task_id="task-supplier-termination",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI TEST",
        standard_version="2021",
        disclosure_id="GRI TEST",
        requirement_id="GRI TEST-supplier-termination",
        requirement_text="percentage of supplier relationships terminated and why.",
        keywords=["终止关系", "供应商"],
        candidate_pages=[67],
        candidate_page_source="contract_candidate",
    )
    chunk = DocumentChunk(
        chunk_id="chunk-supplier-termination",
        report_id="report-1",
        text="评估后终止关系的供应商百分比（%） 0",
        source_page=67,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence[0].metadata["decision_source"] == "contract_guardrail+ontology_matrix"
    assert result.assessment.missing_items.count("终止关系原因说明") == 1
    assert "终止关系百分比" in result.assessment.missing_items


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


def test_disclosure_agent_marks_english_and_short_omission_terms():
    cases = [
        ("GRI 304-4-a", "304-4 Species affected not applicable", "not_applicable"),
        ("GRI 201-1-a", "201-1 Direct economic value generated confidentiality constraints", "confidentiality"),
        ("GRI 304-4-a", "304-4 受运营影响的栖息地中已被列入 不适用从略披露", "not_applicable"),
    ]
    for requirement_id, text, reason in cases:
        disclosure_id = "GRI " + requirement_id.removeprefix("GRI ").rsplit("-", 1)[0]
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.split("-")[0],
            standard_version="2021",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="omitted disclosure.",
            keywords=["从略披露", "not applicable", "confidentiality"],
            candidate_pages=[74],
            candidate_page_source="gri_report_index_omission_note",
            index_page=74,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text=text,
            source_page=74,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
        assert result.assessment.evidence[0].metadata["omission_reason"] == reason


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


def test_disclosure_agent_marks_all_governance_kpi_page_68_as_complex_table():
    task = DisclosureTask(
        task_id="task-GRI 205-3-b",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 205",
        standard_version="2016",
        disclosure_id="GRI 205-3",
        requirement_id="GRI 205-3-b",
        requirement_text="Total number of confirmed incidents in which employees were dismissed or disciplined for corruption.",
        keywords=["员工因腐败被开除或受到处分的事件数量"],
        candidate_pages=[68],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=73,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-GRI 205-3-b-68",
        report_id="report-1",
        text="员工因腐败被开除或受到处分的事件数量",
        source_page=68,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[0].quality_flags


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


def test_disclosure_agent_handles_305_1_scope_1_and_method_rules():
    cases = [
        ("GRI 305-1-a", [(20, "范围一温室气体排放量 10,000 tCO2e"), (63, "范围一温室气体排放量 KPI")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED),
        ("GRI 305-1-e", [(64, "温室气体核算方法 排放因子 全球变暖潜势 GWP")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW),
        ("GRI 305-1-g", [(64, "温室气体核算方法 GHG Protocol ISO 14064")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW),
    ]
    for requirement_id, page_texts, verdict, review_status in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 305",
            standard_version="2016",
            disclosure_id="GRI 305-1",
            requirement_id=requirement_id,
            requirement_text="direct GHG emissions or calculation methodology.",
            keywords=["范围一", "温室气体", "排放因子", "核算方法"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=74,
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
        assert [item.source_page for item in result.assessment.evidence] == [page for page, _ in page_texts]
        if 63 in [page for page, _ in page_texts]:
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_replaces_invalid_305_2_page_3_with_scope_2_kpi_pages():
    cases = [
        ("GRI 305-2-a", "范围二（基于位置）57,897.05 tCO2e"),
        ("GRI 305-2-b", "范围二（基于市场）绿色电力抵扣后排放量"),
    ]
    for requirement_id, scope_text in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 305",
            standard_version="2016",
            disclosure_id="GRI 305-2",
            requirement_id=requirement_id,
            requirement_text="energy indirect Scope 2 GHG emissions.",
            keywords=["TCFD", "范围二", "温室气体"],
            candidate_pages=[20, 63],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=74,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-3",
                report_id="report-1",
                text="TCFD 气候相关财务信息披露工作组 RE100 联系邮箱。",
                source_page=3,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            ),
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-20",
                report_id="report-1",
                text=scope_text,
                source_page=20,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            ),
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-63",
                report_id="report-1",
                text=f"总耗水量(t) 277,323.60 177,280.10 69,292.00 {scope_text} 化学需氧量(kg) 11,973.00",
                source_page=63,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            ),
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
        assert [item.source_page for item in result.assessment.evidence] == [20, 63]
        assert all(item.source_page != 3 for item in result.assessment.evidence)
        assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags
        assert "范围二" in result.assessment.evidence[-1].evidence_preview
        assert "总耗水量" not in result.assessment.evidence[-1].evidence_preview


def test_disclosure_agent_keeps_unreported_305_1_and_305_2_subitems_unknown():
    cases = [
        ("GRI 305-1-d", "GRI 305-1"),
        ("GRI 305-1-d-i", "GRI 305-1"),
        ("GRI 305-1-d-ii", "GRI 305-1"),
        ("GRI 305-1-d-iii", "GRI 305-1"),
        ("GRI 305-1-f", "GRI 305-1"),
        ("GRI 305-2-c", "GRI 305-2"),
        ("GRI 305-2-d", "GRI 305-2"),
    ]
    for requirement_id, disclosure_id in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 305",
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="unreported GHG subitem.",
            keywords=["温室气体", "范围一", "范围二", "排放因子"],
            candidate_pages=[20, 63, 64],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=74,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-63",
                report_id="report-1",
                text="范围一 范围二 温室气体 KPI 排放因子 核算方法。",
                source_page=63,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
            )
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence == []


def test_disclosure_agent_uses_ghg_methodology_page_for_305_2_g():
    task = DisclosureTask(
        task_id="task-GRI 305-2-g",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 305",
        standard_version="2016",
        disclosure_id="GRI 305-2",
        requirement_id="GRI 305-2-g",
        requirement_text="Standards, methodologies, assumptions, and/or calculation tools used.",
        keywords=["Standards", "温室气体核算方法", "排放因子"],
        candidate_pages=[3, 64],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=74,
    )
    chunks = [
        DocumentChunk(
            chunk_id="chunk-GRI 305-2-g-3",
            report_id="report-1",
            text="GRI Standards ESG报告编制依据。",
            source_page=3,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-GRI 305-2-g-64",
            report_id="report-1",
            text="温室气体核算方法 排放因子来源 范围二 购买的电力和热力基于消费及相应排放因子进行计算。",
            source_page=64,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert [item.source_page for item in result.assessment.evidence] == [64]


def test_disclosure_agent_uses_emission_factor_sources_for_305_2_e():
    task = DisclosureTask(
        task_id="task-GRI 305-2-e",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 305",
        standard_version="2016",
        disclosure_id="GRI 305-2",
        requirement_id="GRI 305-2-e",
        requirement_text="Source of the emission factors and the global warming potential rates used.",
        keywords=["排放因子来源", "GWP", "范围二"],
        candidate_pages=[64],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=74,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-GRI 305-2-e-64",
        report_id="report-1",
        text="温室气体核算方法 排放因子来源 范围二 生态环境部 发改委 BEIS IEA AIB Green-e。",
        source_page=64,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert [item.source_page for item in result.assessment.evidence] == [64]


def test_disclosure_agent_handles_scope_3_total_and_methodology_rules():
    cases = [
        (
            "GRI 305-3-a",
            "other indirect Scope 3 GHG emissions.",
            [(20, "范围三排放总量 4,944,060.00 tCO2e"), (63, "范围三 - 排放总量(tCO2e) 4,944,060.00")],
            AssessmentVerdict.DISCLOSED,
            ReviewStatus.NOT_REQUIRED,
            [20, 63],
        ),
        (
            "GRI 305-3-f",
            "Source of emission factors and GWP rates used.",
            [(64, "范围三 排放因子来源 Sphera Ecoinvent BEIS 生态环境部通知")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [64],
        ),
    ]
    for requirement_id, requirement_text, page_texts, verdict, review_status, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 305",
            standard_version="2016",
            disclosure_id="GRI 305-3",
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            keywords=["范围三", "排放总量", "排放因子来源"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=74,
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
        if requirement_id == "GRI 305-3-a":
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_305_5_direct_reduction_kpi():
    task = DisclosureTask(
        task_id="task-GRI 305-5-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 305",
        standard_version="2016",
        disclosure_id="GRI 305-5",
        requirement_id="GRI 305-5-a",
        requirement_text="GHG emissions reduced as a direct result of reduction initiatives.",
        keywords=["节能措施促成的碳减排总量", "碳减排"],
        candidate_pages=[63],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=74,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-GRI 305-5-a-63",
        report_id="report-1",
        text="节能措施促成的碳减排总量(tCO2e) 158.06 246.31 256.17",
        source_page=63,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
    assert [item.source_page for item in result.assessment.evidence] == [63]
    assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[0].quality_flags


def test_disclosure_agent_does_not_use_waste_or_water_pollutants_for_305_7_air_emissions():
    task = DisclosureTask(
        task_id="task-GRI 305-7-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 305",
        standard_version="2016",
        disclosure_id="GRI 305-7",
        requirement_id="GRI 305-7-a",
        requirement_text="Significant air emissions including NOx, SOx, POP, VOC, HAP, PM, and other standard categories.",
        keywords=["NOx", "SOx", "污染物排放总量", "废弃物"],
        candidate_pages=[21, 63],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=74,
    )
    chunks = [
        DocumentChunk(
            chunk_id="chunk-GRI 305-7-a-21",
            report_id="report-1",
            text="废弃物管理 回用 Reuse 化学品桶危废减量。",
            source_page=21,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-GRI 305-7-a-63",
            report_id="report-1",
            text="污染物排放总量 化学需氧量 悬浮物 氨氮 总磷 总氮。",
            source_page=63,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []


def test_disclosure_agent_keeps_306_4_reuse_subitems_partial_for_case_evidence():
    for requirement_id in ["GRI 306-4-b-i", "GRI 306-4-c-i"]:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 306",
            standard_version="2020",
            disclosure_id="GRI 306-4",
            requirement_id=requirement_id,
            requirement_text="Preparation for reuse.",
            keywords=["回用", "Reuse", "废弃物回收总量"],
            candidate_pages=[21, 64],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=74,
        )
        chunks = [
            DocumentChunk(
                chunk_id=f"chunk-{requirement_id}-21",
                report_id="report-1",
                text="回用（Reuse）循环使用金属框架和包装箱运输大型部件，回收再用供应商回运的木箱和金属支架。",
                source_page=21,
                source_method=EvidenceSourceMethod.PDFPLUMBER,
                source_file_hash="hash-1",
                quality_flags=[PageQualityFlag.COMPLEX_TABLE],
            )
        ]

        result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == [21]


def test_disclosure_agent_handles_306_waste_management_and_kpi_partial_rules():
    cases = [
        ("GRI 306-1-a", "waste-related impacts.", [(21, "废弃物管理 包装材料周转 化学品清洗废液 化学品桶危废减量"), (22, "废水分类处理 回用")]),
        ("GRI 306-1-a-i", "inputs activities outputs that lead to waste impacts.", [(21, "包装材料周转 化学品清洗废液 化学品桶危废减量")]),
        ("GRI 306-1-a-ii", "waste-related impacts in own activities and value chain.", [(21, "供应商回运木箱和金属支架 包装箱运输大型部件")]),
        ("GRI 306-2-a", "actions to prevent waste generation and manage impacts.", [(21, "5R原则 循环包装 废液减量 衬膜改造")]),
        ("GRI 306-2-b", "third-party waste management and recovery operations.", [(21, "处置供应商资质审查与监督")]),
        ("GRI 306-3-a", "total weight of waste generated and breakdown.", [(64, "危险废物总重(t) 4,692.00 非危险废物总重(t) 27,430.00")]),
        ("GRI 306-4-a", "total weight of waste diverted from disposal.", [(64, "废弃物回收总量(t) 22,977.22 废弃物回收率(%) 72")]),
        ("GRI 306-4-b", "hazardous waste diverted from disposal.", [(64, "危险废物回收总量(t) 374.00 危险废物回收率(%) 8")]),
        ("GRI 306-4-c", "non-hazardous waste diverted from disposal.", [(64, "非危险废物回收总量(t) 22,603.22 非危险废物回收率(%) 82")]),
    ]
    for requirement_id, requirement_text, page_texts in cases:
        disclosure_id = "GRI 306-1" if requirement_id.startswith("GRI 306-1") else ("GRI 306-2" if requirement_id.startswith("GRI 306-2") else ("GRI 306-3" if requirement_id.startswith("GRI 306-3") else "GRI 306-4"))
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 306",
            standard_version="2020",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            keywords=["废弃物", "回收总量", "5R", "供应商资质"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=74,
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
        if any(page == 64 for page, _ in page_texts):
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_308_supplier_environmental_assessment_rules():
    cases = [
        ("GRI 308-1-a", [(67, "使用环境评价维度筛选的新供应商百分比（%） 100")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [67]),
        ("GRI 308-2-a", [(67, "开展环境影响评估的供应商数量（个）")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [67]),
        ("GRI 308-2-b", [(67, "具有重大实际/潜在负面环境影响的供应商数量（个）")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [67]),
        ("GRI 308-2-c", [(52, "供应商环境影响管理背景"), (67, "具有重大实际/潜在负面环境影响的供应商数量（个） 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [52, 67]),
        ("GRI 308-2-d", [(67, "具有重大实际/潜在负面环境影响，且评估后一致同意改进的供应商百分比（%）")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [67]),
        ("GRI 308-2-e", [(54, "供应商退出机制"), (67, "评估后终止关系的供应商百分比（%）")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [54, 67]),
    ]
    for requirement_id, page_texts, verdict, review_status, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 308",
            standard_version="2016",
            disclosure_id="GRI 308-1" if requirement_id.startswith("GRI 308-1") else "GRI 308-2",
            requirement_id=requirement_id,
            requirement_text="supplier environmental assessment requirement.",
            keywords=["供应商", "环境影响评估", "环境评价维度", "终止关系"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=75,
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
        if 67 in expected_pages:
            kpi_evidence = next(item for item in result.assessment.evidence if item.source_page == 67)
            assert PageQualityFlag.COMPLEX_TABLE in kpi_evidence.quality_flags
            assert kpi_evidence.is_kpi_evidence is True
            assert kpi_evidence.metadata["evidence_kind"] == "kpi_value"
            assert any(term in kpi_evidence.evidence_preview for term in task.keywords)


def test_disclosure_agent_handles_401_employment_rules():
    cases = [
        ("GRI 401-1-a", "GRI 401-1", [(33, "新进员工总数 性别 年龄结构"), (65, "新进员工总数 新进员工性别结构 新进员工年龄结构")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [33, 65]),
        ("GRI 401-1-b", "GRI 401-1", [(33, "离职员工性别 年龄结构 员工流失率"), (65, "离职员工性别结构 离职员工年龄结构 员工流失率")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [33, 65]),
        ("GRI 401-2-a", "GRI 401-2", [(34, "薪酬福利 医疗保险 带薪假期 育儿假 补充商业医疗 补充住房公积金")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [34]),
        ("GRI 401-2-a-ii", "GRI 401-2", [(34, "医疗保险 补充商业医疗 定期体检")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [34]),
        ("GRI 401-2-a-iv", "GRI 401-2", [(34, "带薪假期 育儿假")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [34]),
        ("GRI 401-2-a-vii", "GRI 401-2", [(34, "补充住房公积金 家庭支持计划")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [34]),
        ("GRI 401-3-c", "GRI 401-3", [(32, "员工关怀正文"), (66, "假期结束返岗男性员工数 假期结束返岗女性员工数")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [66]),
        ("GRI 401-3-d", "GRI 401-3", [(32, "员工关怀正文"), (66, "假期结束返岗且12个月后仍在职男性员工数量 假期结束返岗且12个月后仍在职女性员工数量")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [66]),
        ("GRI 401-3-e", "GRI 401-3", [(32, "员工关怀正文"), (66, "返岗率 留任率 男性员工数 女性员工数")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [66]),
    ]
    for requirement_id, disclosure_id, page_texts, verdict, review_status, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 401",
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="employment requirement.",
            keywords=["新进员工", "离职员工", "福利", "育儿假", "返岗", "留任"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=75,
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
        if any(page in {65, 66} for page in expected_pages):
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_402_labor_relations_notice_period():
    task = DisclosureTask(
        task_id="task-GRI 402-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 402",
        standard_version="2016",
        disclosure_id="GRI 402-1",
        requirement_id="GRI 402-1-a",
        requirement_text="Minimum number of weeks' notice typically provided to employees prior to significant operational changes.",
        keywords=["提前通知", "最短周数", "重大运营变更"],
        candidate_pages=[33, 66],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=75,
    )
    chunks = [
        DocumentChunk(
            chunk_id="chunk-GRI 402-1-a-33",
            report_id="report-1",
            text="重大运营变更前提前4周通知员工",
            source_page=33,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-GRI 402-1-a-66",
            report_id="report-1",
            text="提前通知员工及其代表的最短周数（周） 4",
            source_page=66,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
    assert [item.source_page for item in result.assessment.evidence] == [33, 66]
    assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_403_ohs_partial_rules():
    cases = [
        ("GRI 403-1-a", [(38, "EHS治理架构 职业健康安全管理体系"), (39, "参照 ISO 45001"), (66, "通过ISO 45001认证的工厂占比 100")]),
        ("GRI 403-1-a-ii", [(38, "EHS治理架构 职业健康安全管理体系"), (39, "参照 ISO 45001"), (66, "通过ISO 45001认证的工厂占比 100")]),
        ("GRI 403-1-b", [(38, "EHS治理架构 职业健康安全管理体系"), (39, "参照 ISO 45001"), (66, "通过ISO 45001认证的工厂占比 100")]),
        ("GRI 403-2-a", [(39, "风险评估 隐患排查 双重预防管控机制 全员隐患上报"), (41, "作业安全风险识别 隐患排查闭环")]),
        ("GRI 403-2-a-i", [(39, "风险评估 隐患排查 双重预防管控机制"), (41, "作业安全风险识别")]),
        ("GRI 403-2-a-ii", [(39, "全员隐患上报 流程指标看板"), (41, "事故事件管理 事故汇报 整改流程")]),
        ("GRI 403-2-b", [(39, "隐患排查 双重预防管控机制"), (41, "隐患排查闭环 事故事件管理")]),
        ("GRI 403-2-d", [(39, "流程指标看板"), (41, "事故汇报和整改流程")]),
        ("GRI 403-3-a", [(38, "环保和职业健康技术专委会"), (66, "员工体检率 100"), (67, "职业病病例数量")]),
        ("GRI 403-4-a", [(38, "多级EHS委员会"), (39, "全员隐患上报"), (41, "全员参与隐患排查"), (66, "由管理层和员工代表组成的健康与安全委员会代表的员工比例 100")]),
        ("GRI 403-4-b", [(38, "多级EHS委员会"), (39, "全员隐患上报"), (41, "全员参与隐患排查"), (66, "由管理层和员工代表组成的健康与安全委员会代表的员工比例 100")]),
        ("GRI 403-5-a", [(41, "EHS培训对象 目的 方式 课程 师资安排 考核"), (66, "EHS培训指标")]),
        ("GRI 403-6-a", [(34, "医疗保险 定期体检 补充商业医疗 家庭支持计划"), (66, "员工体检率"), (67, "职业病病例数量")]),
    ]
    for requirement_id, page_texts in cases:
        disclosure_id = "-".join(requirement_id.split("-")[:3])
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 403",
            standard_version="2018",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="occupational health and safety requirement.",
            keywords=["EHS", "职业健康", "安全", "隐患", "培训", "体检"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=75,
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
        if any(page in {66, 67} for page in [page for page, _ in page_texts]):
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_403_6_to_403_8_followup_rules():
    cases = [
        (
            "GRI 403-6-b",
            [(34, "定期体检 医疗保险 补充商业医疗"), (67, "员工体检率 100%")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [34, 67],
        ),
        (
            "GRI 403-7-a",
            [(38, "外部供应商 EHS 管理"), (39, "岗位资格培训 定期复训"), (41, "承包商施工方案安全审查"), (52, "供应商管理"), (54, "供应商培训")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [38, 39, 41, 52, 54],
        ),
        (
            "GRI 403-8-a",
            [(38, "职业健康安全管理体系"), (39, "ISO 45001"), (66, "通过ISO 45001认证的工厂占比 100%")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [38, 39, 66],
        ),
        (
            "GRI 403-8-a-i",
            [(66, "通过ISO 45001认证的工厂占比 100%")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [66],
        ),
        (
            "GRI 403-8-a-ii",
            [(66, "ISO 45001 工厂占比 100%")],
            AssessmentVerdict.UNKNOWN,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [],
        ),
        (
            "GRI 403-8-a-iii",
            [(66, "通过ISO 45001认证的工厂占比 100%")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [66],
        ),
        (
            "GRI 403-8-b",
            [(66, "通过ISO 45001认证的工厂占比 100%")],
            AssessmentVerdict.UNKNOWN,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [],
        ),
        (
            "GRI 403-8-c",
            [(66, "通过ISO 45001认证的工厂占比 100%")],
            AssessmentVerdict.UNKNOWN,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [],
        ),
    ]
    for requirement_id, page_texts, verdict, review_status, expected_pages in cases:
        disclosure_id = "GRI " + "-".join(requirement_id.split(" ", 1)[1].split("-")[:2])
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 403",
            standard_version="2018",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="occupational health and safety coverage requirement.",
            keywords=["职业健康", "ISO 45001", "体检", "供应商", "EHS"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=75,
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
        if any(page in {66, 67} for page in expected_pages):
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_403_9_work_injury_kpi_rules():
    cases = [
        ("GRI 403-9-a", [(40, "员工工伤管理 高后果工伤风险"), (67, "员工可记录工伤数量 13 TRIR 0.29 死亡数量 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [40, 67]),
        ("GRI 403-9-a-i", [(67, "员工工伤死亡数量 0 死亡率 0")], AssessmentVerdict.DISCLOSED, [67]),
        ("GRI 403-9-a-ii", [(67, "员工损失工时事故率 LTIR")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-9-a-iii", [(67, "员工可记录工伤数量 13 TRIR 0.29")], AssessmentVerdict.DISCLOSED, [67]),
        ("GRI 403-9-a-iv", [(67, "员工可记录工伤数量 13")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-9-a-v", [(67, "员工工作小时数 44,528,901")], AssessmentVerdict.DISCLOSED, [67]),
        ("GRI 403-9-b", [(67, "外部供方工作小时数 TRIR LTIR 可记录工伤数量 死亡数量")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-9-b-i", [(67, "外部供方工伤死亡数量 0 死亡率 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-9-b-ii", [(67, "外部供方 LTIR")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-9-b-iii", [(67, "外部供方可记录工伤数量 TRIR")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-9-b-iv", [(67, "外部供方可记录工伤数量")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-9-b-v", [(67, "外部供方工作小时数")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-9-c", [(40, "主要工伤风险"), (67, "可记录工伤 KPI")], AssessmentVerdict.PARTIALLY_DISCLOSED, [40, 67]),
        ("GRI 403-9-c-i", [(40, "高后果工伤风险 管控措施")], AssessmentVerdict.PARTIALLY_DISCLOSED, [40]),
        ("GRI 403-9-c-ii", [(67, "工伤 KPI")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-9-c-iii", [(40, "工伤风险管控措施")], AssessmentVerdict.PARTIALLY_DISCLOSED, [40]),
        ("GRI 403-9-d", [(40, "事故调查 整改闭环"), (67, "TRIR LTIR")], AssessmentVerdict.PARTIALLY_DISCLOSED, [40, 67]),
        ("GRI 403-9-e", [(67, "TRIR 和 LTIR 按百万工时计算")], AssessmentVerdict.DISCLOSED, [67]),
        ("GRI 403-9-f", [(67, "TRIR LTIR")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-9-g", [(67, "TRIR LTIR")], AssessmentVerdict.UNKNOWN, []),
    ]
    for requirement_id, page_texts, verdict, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 403",
            standard_version="2018",
            disclosure_id="GRI 403-9",
            requirement_id=requirement_id,
            requirement_text="work-related injury requirement.",
            keywords=["TRIR", "LTIR", "工伤", "工作小时数", "死亡"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=75,
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
        assert result.assessment.review_status is (
            ReviewStatus.NOT_REQUIRED if verdict is AssessmentVerdict.DISCLOSED else ReviewStatus.NEEDS_MANUAL_REVIEW
        )
        assert [item.source_page for item in result.assessment.evidence] == expected_pages
        if 67 in expected_pages:
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_403_10_ill_health_kpi_rules():
    cases = [
        ("GRI 403-10-a", [(67, "员工职业病病例数量 0 工作相关健康问题导致死亡数 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-10-a-i", [(67, "员工工作相关健康问题导致死亡数 0")], AssessmentVerdict.DISCLOSED, [67]),
        ("GRI 403-10-a-ii", [(67, "员工职业病病例数量 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-10-a-iii", [(67, "员工职业病病例数量 0")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-10-b", [(67, "外部供方职业病病例数量 0 工作相关健康问题导致死亡数 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-10-b-i", [(67, "外部供方工作相关健康问题导致死亡数 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-10-b-ii", [(67, "外部供方职业病病例数量 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [67]),
        ("GRI 403-10-b-iii", [(67, "外部供方职业病病例数量 0")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-10-c", [(38, "职业健康风险管理"), (67, "职业病病例数量 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [38, 67]),
        ("GRI 403-10-c-i", [(38, "职业健康风险管理"), (67, "职业病病例数量 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, [38, 67]),
        ("GRI 403-10-c-ii", [(67, "职业病病例数量 0")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-10-c-iii", [(38, "职业健康风险管控措施")], AssessmentVerdict.PARTIALLY_DISCLOSED, [38]),
        ("GRI 403-10-d", [(67, "职业病病例数量 0")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 403-10-e", [(67, "职业病病例数量 0")], AssessmentVerdict.UNKNOWN, []),
    ]
    for requirement_id, page_texts, verdict, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 403",
            standard_version="2018",
            disclosure_id="GRI 403-10",
            requirement_id=requirement_id,
            requirement_text="work-related ill health requirement.",
            keywords=["职业病", "工作相关健康问题", "死亡", "职业健康"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=75,
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
        assert result.assessment.review_status is (
            ReviewStatus.NOT_REQUIRED if verdict is AssessmentVerdict.DISCLOSED else ReviewStatus.NEEDS_MANUAL_REVIEW
        )
        assert [item.source_page for item in result.assessment.evidence] == expected_pages
        if 67 in expected_pages:
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_404_and_405_partial_rules():
    cases = [
        ("GRI 404-1-a", "GRI 404-1", [(35, "员工培训总时数 259,036 小时 人均受训 56.30 小时"), (66, "员工培训总时数 人均受训小时")], AssessmentVerdict.PARTIALLY_DISCLOSED, [35, 66]),
        ("GRI 404-1-a-i", "GRI 404-1", [(66, "员工培训总时数 人均受训小时")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 404-1-a-ii", "GRI 404-1", [(66, "员工培训总时数 人均受训小时")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 404-2-a", "GRI 404-2", [(35, "员工发展手册 横向 纵向发展路径"), (36, "智慧制造训战 女性领导力 管理能力 专业培训 导师计划"), (41, "EHS 培训")], AssessmentVerdict.PARTIALLY_DISCLOSED, [35, 36, 41]),
        ("GRI 404-2-b", "GRI 404-2", [(35, "员工发展手册 培训项目")], AssessmentVerdict.UNKNOWN, []),
        ("GRI 404-3-a", "GRI 404-3", [(35, "绩效和职业发展考核"), (66, "接受定期绩效和职业发展考核的员工比例 100%")], AssessmentVerdict.PARTIALLY_DISCLOSED, [35, 66]),
        ("GRI 405-1-a", "GRI 405-1", [(33, "女性高管比例 管理层年龄 少数民族高管比例 外籍高管比例"), (65, "管理层年龄 女性高管比例 少数民族高管比例 外籍高管比例")], AssessmentVerdict.PARTIALLY_DISCLOSED, [33, 65]),
        ("GRI 405-1-a-i", "GRI 405-1", [(33, "女性高管比例 管理层年龄 少数民族高管比例 外籍高管比例"), (65, "管理层年龄 女性高管比例 少数民族高管比例 外籍高管比例")], AssessmentVerdict.PARTIALLY_DISCLOSED, [33, 65]),
        ("GRI 405-2-a", "GRI 405-2", [(33, "员工性别结构 员工职级结构"), (65, "员工性别结构 管理层年龄"), (66, "同级别女性员工平均总时薪占男性员工平均总时薪的 100%")], AssessmentVerdict.PARTIALLY_DISCLOSED, [33, 65, 66]),
    ]
    for requirement_id, disclosure_id, page_texts, verdict, expected_pages in cases:
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.rsplit("-", 1)[0],
            standard_version="2016",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="training or diversity requirement.",
            keywords=["培训", "绩效", "职业发展", "女性高管", "管理层"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=75,
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
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert [item.source_page for item in result.assessment.evidence] == expected_pages
        if any(page in {65, 66} for page in expected_pages):
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_does_not_use_generic_pages_for_405_2_pay_ratio():
    task = DisclosureTask(
        task_id="task-GRI 405-2-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 405",
        standard_version="2016",
        disclosure_id="GRI 405-2",
        requirement_id="GRI 405-2-a",
        requirement_text="Ratio of the basic salary and remuneration of women to men for each employee category, by significant locations of operation.",
        keywords=["报告边界", "多样化", "供应商", "温室气体"],
        candidate_pages=[3, 25, 53, 64],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=75,
    )
    chunks = [
        DocumentChunk(
            chunk_id="chunk-GRI 405-2-a-3",
            report_id="report-1",
            text="报告边界包含远景能源所有实际运营场所。",
            source_page=3,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-GRI 405-2-a-25",
            report_id="report-1",
            text="多样化的节水举措。",
            source_page=25,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-GRI 405-2-a-53",
            report_id="report-1",
            text="供应商行为准则。",
            source_page=53,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-GRI 405-2-a-64",
            report_id="report-1",
            text="温室气体核算方法。",
            source_page=64,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    result = DisclosureAgent().analyze(task, chunks, confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []


def test_disclosure_agent_handles_406_to_409_human_rights_boundary_rules():
    cases = [
        ("GRI 406-1-a", "GRI 406-1", [(32, "报告期内，公司无歧视事件发生")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [32]),
        ("GRI 406-1-b", "GRI 406-1", [(32, "报告期内，公司无歧视事件发生")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 406-1-b-i", "GRI 406-1", [(32, "报告期内，公司无歧视事件发生")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 406-1-b-ii", "GRI 406-1", [(32, "报告期内，公司无歧视事件发生")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 406-1-b-iii", "GRI 406-1", [(32, "报告期内，公司无歧视事件发生")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 406-1-b-iv", "GRI 406-1", [(32, "报告期内，公司无歧视事件发生")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 407-1-a", "GRI 407-1", [(33, "集体协议覆盖率 100% 正式选举职工代表覆盖率 100%")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 407-1-a-i", "GRI 407-1", [(33, "集体协议覆盖率 100%")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 407-1-a-ii", "GRI 407-1", [(66, "正式选举职工代表覆盖率 100%")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 407-1-b", "GRI 407-1", [(33, "员工代表 沟通机制"), (66, "集体协议覆盖率 100% 正式选举职工代表覆盖率 100%")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [33, 66]),
        ("GRI 408-1-a", "GRI 408-1", [(32, "禁止使用童工及童工补救管理 青年员工保护"), (52, "供应商行为准则"), (53, "供应商社会责任尽调 审计")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [32, 52, 53]),
        ("GRI 408-1-a-i", "GRI 408-1", [(32, "禁止使用童工政策"), (52, "供应商不得使用童工")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [32, 52]),
        ("GRI 408-1-a-ii", "GRI 408-1", [(32, "禁止使用童工及青年员工保护管理细则"), (52, "供应商不得使用童工"), (53, "供应商筛查 尽调 审计")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [32, 52, 53]),
        ("GRI 408-1-b", "GRI 408-1", [(32, "禁止使用童工政策")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 408-1-b-i", "GRI 408-1", [(52, "供应商不得使用童工")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 408-1-b-ii", "GRI 408-1", [(52, "供应商不得使用童工")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 408-1-c", "GRI 408-1", [(32, "禁止使用童工及青年员工保护"), (52, "供应商不得使用童工"), (53, "供应商筛查 尽调 审计")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [32, 52, 53]),
        ("GRI 409-1-a", "GRI 409-1", [(32, "防止强迫性劳动管理细则"), (52, "供应商劳工与人权准则"), (53, "英国现代奴役法 尽调流程")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [32, 52, 53]),
        ("GRI 409-1-a-i", "GRI 409-1", [(32, "防止强迫性劳动管理细则")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 409-1-a-ii", "GRI 409-1", [(52, "供应商劳工与人权准则")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 409-1-b", "GRI 409-1", [(32, "防止强迫性劳动管理细则"), (52, "供应商劳工与人权准则"), (53, "英国现代奴役法 尽调流程")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [32, 52, 53]),
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
            requirement_text="human rights boundary requirement.",
            keywords=["歧视", "集体协议", "童工", "强迫劳动", "供应商"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=76,
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
        if 66 in expected_pages:
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_413_and_414_community_and_supplier_social_rules():
    cases = [
        ("GRI 413-1-a", "GRI 413-1", [(14, "利益相关方识别与沟通"), (42, "乡村振兴 教育帮扶"), (43, "森林保护"), (44, "社区捐赠 公益项目")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [14, 42, 43, 44]),
        ("GRI 413-1-a-i", "GRI 413-1", [(14, "利益相关方识别与沟通")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-1-a-ii", "GRI 413-1", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-1-a-iii", "GRI 413-1", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-1-a-iv", "GRI 413-1", [(14, "利益相关方识别与沟通"), (42, "社区发展项目")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [14, 42]),
        ("GRI 413-1-a-v", "GRI 413-1", [(14, "利益相关方类别 关注议题 沟通渠道"), (42, "乡村振兴 教育帮扶"), (43, "森林保护"), (44, "公益项目")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [14, 42, 43, 44]),
        ("GRI 413-1-a-vi", "GRI 413-1", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-1-a-vii", "GRI 413-1", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-1-a-viii", "GRI 413-1", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-2-a", "GRI 413-2", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-2-a-i", "GRI 413-2", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 413-2-a-ii", "GRI 413-2", [(42, "社区项目")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
        ("GRI 414-1-a", "GRI 414-1", [(67, "使用社会评价维度筛选的新供应商百分比（%） 100")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [67]),
        ("GRI 414-2-a", "GRI 414-2", [(67, "开展社会影响评估的供应商数量（个） 85")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [67]),
        ("GRI 414-2-b", "GRI 414-2", [(67, "具有重大实际/潜在负面社会影响的供应商数量（个） 0")], AssessmentVerdict.DISCLOSED, ReviewStatus.NOT_REQUIRED, [67]),
        ("GRI 414-2-c", "GRI 414-2", [(52, "供应商社会责任管理"), (67, "具有重大实际/潜在负面社会影响的供应商数量（个） 0")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [52, 67]),
        ("GRI 414-2-d", "GRI 414-2", [(54, "供应商改进机制"), (67, "参与改进行动的供应商数量")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [54, 67]),
        ("GRI 414-2-e", "GRI 414-2", [(54, "供应商退出机制"), (67, "终止关系的供应商")], AssessmentVerdict.PARTIALLY_DISCLOSED, ReviewStatus.NEEDS_MANUAL_REVIEW, [54, 67]),
        ("GRI 416-1-a", "GRI 416-1", [(46, "产品质量和安全管理体系 产品开发安全风险管理流程")], AssessmentVerdict.UNKNOWN, ReviewStatus.NEEDS_MANUAL_REVIEW, []),
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
            requirement_text="community or supplier social requirement.",
            keywords=["社区", "供应商", "社会影响", "产品质量"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=76,
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
        if 67 in expected_pages:
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_handles_416_417_418_product_and_privacy_rules():
    cases = [
        (
            "GRI 416-2-a",
            "GRI 416-2",
            [(46, "未发生因产品质量安全而导致客户健康安全受到伤害的事件")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [46],
        ),
        (
            "GRI 416-2-a-i",
            "GRI 416-2",
            [(46, "未发生因产品质量安全而导致客户健康安全受到伤害的事件")],
            AssessmentVerdict.UNKNOWN,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [],
        ),
        (
            "GRI 416-2-b",
            "GRI 416-2",
            [(46, "未发生因产品质量安全而导致客户健康安全受到伤害的事件")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [46],
        ),
        (
            "GRI 417-1-a",
            "GRI 417-1",
            [(46, "产品说明书介绍潜在环境、健康与安全影响及注意事项")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [46],
        ),
        (
            "GRI 417-1-a-ii",
            "GRI 417-1",
            [(46, "产品说明书介绍潜在环境、健康与安全影响及注意事项")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [46],
        ),
        (
            "GRI 417-1-a-iii",
            "GRI 417-1",
            [(46, "产品说明书介绍潜在环境、健康与安全影响及注意事项")],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [46],
        ),
        (
            "GRI 417-2-a",
            "GRI 417-2",
            [(46, "产品说明书介绍潜在环境、健康与安全影响及注意事项")],
            AssessmentVerdict.UNKNOWN,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [],
        ),
        (
            "GRI 418-1-a",
            "GRI 418-1",
            [(61, "报告期内未接到任何涉及侵犯客户隐私或数据丢失的投诉")],
            AssessmentVerdict.DISCLOSED,
            ReviewStatus.NOT_REQUIRED,
            [61],
        ),
        (
            "GRI 418-1-a-i",
            "GRI 418-1",
            [(61, "报告期内未接到任何涉及侵犯客户隐私或数据丢失的投诉")],
            AssessmentVerdict.UNKNOWN,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [],
        ),
        (
            "GRI 418-1-b",
            "GRI 418-1",
            [
                (60, "客户数据保护 DLP 数据泄露风险监控"),
                (61, "报告期内未接到任何涉及侵犯客户隐私或数据丢失的投诉"),
                (68, "信息安全 KPI 数据泄露风险监控"),
            ],
            AssessmentVerdict.PARTIALLY_DISCLOSED,
            ReviewStatus.NEEDS_MANUAL_REVIEW,
            [60, 61, 68],
        ),
        (
            "GRI 418-1-c",
            "GRI 418-1",
            [(61, "报告期内未接到任何涉及侵犯客户隐私或数据丢失的投诉")],
            AssessmentVerdict.DISCLOSED,
            ReviewStatus.NOT_REQUIRED,
            [61],
        ),
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
            requirement_text="product responsibility or customer privacy requirement.",
            keywords=["产品说明书", "产品质量安全", "客户隐私", "数据丢失", "投诉"],
            candidate_pages=[page for page, _ in page_texts],
            candidate_page_source="gri_report_index+requirement_supplement",
            index_page=76,
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
        if 68 in expected_pages:
            assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[-1].quality_flags


def test_disclosure_agent_applies_compilation_guardrail_missing_items_without_creating_evidence():
    task = DisclosureTask(
        task_id="task-GRI 416-2-a-i",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 416",
        standard_version="2016",
        disclosure_id="GRI 416-2",
        requirement_id="GRI 416-2-a-i",
        requirement_text="incidents of non-compliance resulting in a fine or penalty;",
        keywords=["产品质量安全", "罚款", "处罚"],
        candidate_pages=[],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=76,
    )

    result = DisclosureAgent().analyze(task, [], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []
    assert "exclude incidents where organization was determined not at fault" in result.assessment.missing_items
