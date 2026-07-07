from src.domain.enums import EvidenceSourceMethod
from src.domain.models import DisclosureTask, DocumentChunk
from src.tools.evidence import chunk_to_evidence
from src.tools.retrieval import retrieve_evidence


def test_retrieve_evidence_returns_keyword_matched_chunks_with_traceability():
    task = DisclosureTask(
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
    chunks = [
        DocumentChunk(
            chunk_id="chunk-1",
            report_id="report-1",
            text="Water use is disclosed.",
            source_page=2,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-2",
            report_id="report-1",
            text="Energy consumption is disclosed for the organization.",
            source_page=5,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    evidence = retrieve_evidence(task, chunks)

    assert len(evidence) == 1
    assert evidence[0].evidence_id == "task-1:chunk-2"
    assert evidence[0].source_page == 5
    assert evidence[0].source_file_hash == "hash-1"


def test_retrieve_evidence_excludes_profile_index_pages_from_global_no_index():
    task = DisclosureTask(
        task_id="task-goldwind-205",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 205-1",
        requirement_id="GRI 205-1-a",
        requirement_text="Disclose corruption risk assessment coverage.",
        keywords=["corruption", "腐败"],
        excluded_pdf_pages=[50, 51],
    )
    chunks = [
        DocumentChunk(
            chunk_id="chunk-index",
            report_id="report-1",
            text="GRI 205：反腐败 2016 205-1 腐败风险评估 P38",
            source_page=50,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="chunk-body",
            report_id="report-1",
            text="The company describes corruption risk assessment controls.",
            source_page=38,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    evidence = retrieve_evidence(task, chunks)

    assert [item.source_page for item in evidence] == [38]
    assert evidence[0].metadata["retrieval_strategy"] == "global_no_index"


def test_chunk_to_evidence_uses_database_safe_id_for_realistic_long_inputs():
    task = DisclosureTask(
        task_id="run-7170e39a373d48ad9d435912ae53bf0d:GRI 302-1-a",
        run_id="run-7170e39a373d48ad9d435912ae53bf0d",
        report_id="report-9d449e2c840744dc8d9bb9561c09e55a",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 302",
        requirement_id="GRI 302-1-a",
        requirement_text="Disclose energy consumption.",
        keywords=["energy"],
    )
    chunk = DocumentChunk(
        chunk_id="report-9d449e2c840744dc8d9bb9561c09e55a-p1-pdfplumber",
        report_id=task.report_id,
        text="Energy consumption is disclosed for the organization.",
        source_page=1,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    evidence = chunk_to_evidence(task, chunk)
    repeated = chunk_to_evidence(task, chunk)

    assert evidence.evidence_id == repeated.evidence_id
    assert evidence.evidence_id.startswith("evidence-")
    assert len(evidence.evidence_id) <= 64
    assert evidence.metadata["task_id"] == task.task_id
    assert evidence.metadata["chunk_id"] == chunk.chunk_id


def test_chunk_to_evidence_builds_preview_around_matched_keyword():
    task = DisclosureTask(
        task_id="task-2-4-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-4",
        requirement_id="GRI 2-4-a",
        requirement_text="report restatements of information.",
        keywords=["信息重述", "无信息重述"],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-index",
        report_id="report-1",
        text=f"{'页首目录文本 ' * 40} 2-4 信息重述 无信息重述 / 2-5 外部鉴证 附录三：鉴证报告 76",
        source_page=71,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    evidence = chunk_to_evidence(task, chunk)

    assert "2-4 信息重述 无信息重述 /" in evidence.evidence_preview
    assert "页首目录文本 页首目录文本 页首目录文本" not in evidence.evidence_preview


def test_chunk_to_evidence_skips_non_matching_header_lines_for_preview():
    task = DisclosureTask(
        task_id="task-2-4-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-4",
        requirement_id="GRI 2-4-a",
        requirement_text="report restatements of information.",
        keywords=["信息重述", "无信息重述"],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-index",
        report_id="report-1",
        text="目录 概述 环境 人 产品 治理 附录\n2-4 信息重述 无信息重述 /\n2-5 外部鉴证 附录三：鉴证报告 76",
        source_page=71,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    evidence = chunk_to_evidence(task, chunk)

    assert evidence.evidence_preview == "2-4 信息重述 无信息重述 /"


def test_chunk_to_evidence_preview_keeps_reporting_period_date_near_keyword():
    task = DisclosureTask(
        task_id="task-2-3-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-3",
        requirement_id="GRI 2-3-a",
        requirement_text="report reporting period and frequency.",
        keywords=["报告期", "报告频率"],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-period",
        report_id="report-1",
        text="本报告覆盖公司2024年1月1日至12月31日\n（以下简称“报告期”）期间的信息和数据。",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    evidence = chunk_to_evidence(task, chunk)

    assert "2024年1月1日至12月31日" in evidence.evidence_preview
    assert "报告期" in evidence.evidence_preview


def test_chunk_to_evidence_preview_prefers_email_over_contact_heading():
    task = DisclosureTask(
        task_id="task-2-3-d",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-3",
        requirement_id="GRI 2-3-d",
        requirement_text="report contact point for questions about the report.",
        keywords=["联系方式", "联系邮箱", "获取及回应本报告", "f_esg_office"],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-contact",
        report_id="report-1",
        text="获取及回应本报告\n欢迎读者提出建议。\nE-mail：f_esg_office@envision-energy.com",
        source_page=3,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    evidence = chunk_to_evidence(task, chunk)

    assert "f_esg_office@envision-energy.com" in evidence.evidence_preview


def test_retrieve_evidence_prefers_candidate_pages_and_records_strategy():
    task = DisclosureTask(
        task_id="run-1:GRI 2-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        requirement_text="report its legal name;",
        keywords=["legal", "name"],
        candidate_pages=[6],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunks = [
        DocumentChunk(
            chunk_id="global",
            report_id="report-1",
            text="legal name appears in unrelated page",
            source_page=1,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
        DocumentChunk(
            chunk_id="bounded",
            report_id="report-1",
            text="legal name Envision Energy",
            source_page=6,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        ),
    ]

    evidence = retrieve_evidence(task, chunks)

    assert [item.source_page for item in evidence] == [6]
    assert evidence[0].metadata["retrieval_strategy"] == "index_page_bounded"
    assert evidence[0].metadata["candidate_pages"] == [6]


def test_retrieve_evidence_falls_back_globally_when_candidate_pages_do_not_match():
    task = DisclosureTask(
        task_id="task-1",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 302",
        requirement_id="GRI 302-1-a",
        requirement_text="Disclose energy consumption.",
        keywords=["energy"],
        candidate_pages=[6],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunks = [
        DocumentChunk(
            chunk_id="global",
            report_id="report-1",
            text="Energy consumption is disclosed.",
            source_page=22,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )
    ]

    evidence = retrieve_evidence(task, chunks)

    assert evidence[0].source_page == 22
    assert evidence[0].metadata["retrieval_strategy"] == "global_fallback"


def test_retrieve_evidence_matches_management_mechanism_terms_on_profile_route():
    task = DisclosureTask(
        task_id="task-205-1-a",
        run_id="run-1",
        report_id="goldwind",
        standard_id="GRI",
        standard_version="2016",
        disclosure_id="GRI 205-1",
        requirement_id="GRI 205-1-a",
        requirement_text="operations assessed for risks related to corruption",
        keywords=["operations", "assessed", "risks", "corruption"],
        candidate_pages=[21],
        candidate_pdf_pages=[21],
        candidate_report_pages=[38],
        candidate_page_source="report_profile",
        kpi_metric_terms=["反腐败", "审计", "商业道德", "舞弊"],
    )
    chunks = [
        DocumentChunk(
            chunk_id="p21",
            report_id="goldwind",
            text="审计委员会领导审计监察部开展反腐败制度建设，按业务单位特点和风险程度制定审计策略，并在审计中关注商业道德问题。",
            source_page=21,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash",
        )
    ]

    evidence = retrieve_evidence(task, chunks)

    assert len(evidence) == 1
    assert evidence[0].source_page == 21
    assert evidence[0].metadata["retrieval_strategy"] == "index_page_bounded"
    assert "反腐败" in evidence[0].evidence_preview
