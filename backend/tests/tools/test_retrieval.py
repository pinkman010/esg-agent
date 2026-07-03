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
