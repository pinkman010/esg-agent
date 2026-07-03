import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from src.agents.disclosure_agent import DisclosureAgent
from src.db.base import Base
from src.db.models import AssessmentRecord, AuditEventRecord, DisclosureTaskRecord, EvidenceItemRecord, RecommendationRecord
from src.db.repositories import Repository
from src.domain.enums import EvidenceSourceMethod, RunStatus
from src.domain.models import AnalysisRun, DisclosureRequirement, DocumentChunk, PageExtraction, Report
from src.services.document_parser import ParsedDocument
from src.workflows.single_report_workflow import SingleReportWorkflow
from tests.database import make_test_engine, reset_database


class FakeParser:
    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        return ParsedDocument(
            report_id=report_id,
            page_count=1,
            pages=[PageExtraction(report_id=report_id, page_number=1, text="Energy consumption is disclosed.")],
            chunks=[
                DocumentChunk(
                    chunk_id="chunk-1",
                    report_id=report_id,
                    text="Energy consumption is disclosed.",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash=source_file_hash,
                )
            ],
            metadata={},
            outline=[],
        )


class FailingParser:
    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        raise RuntimeError("parse failed")


class IndexParser:
    def parse_pdf(self, pdf_path, report_id, source_file_hash, ocr_pages=None):
        return ParsedDocument(
            report_id=report_id,
            page_count=71,
            pages=[
                PageExtraction(
                    report_id=report_id,
                    page_number=71,
                    text="2-1 组织详细情况 关于远景能源 5",
                )
            ],
            chunks=[
                DocumentChunk(
                    chunk_id="chunk-page-1",
                    report_id=report_id,
                    text="legal name appears on the wrong page",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash=source_file_hash,
                ),
                DocumentChunk(
                    chunk_id="chunk-page-6",
                    report_id=report_id,
                    text="Legal name: Envision Energy Co., Ltd.",
                    source_page=6,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash=source_file_hash,
                ),
            ],
            metadata={},
            outline=[],
        )


class FakeAdapter:
    def load_requirements(self):
        return [
            DisclosureRequirement(
                standard_id="GRI 2",
                standard_version="2021",
                disclosure_id="GRI 2-1",
                requirement_id="GRI 2-1-a",
                requirement_text="report its legal name;",
                keywords=["legal", "name"],
            )
        ]

    def build_tasks(self, run_id, report_id):
        return [requirement_to_task(self.load_requirements()[0], run_id, report_id)]


def requirement_to_task(requirement, run_id, report_id):
    from src.domain.models import DisclosureTask

    return DisclosureTask(
        task_id=f"{run_id}:{requirement.requirement_id}",
        run_id=run_id,
        report_id=report_id,
        standard_id=requirement.standard_id,
        standard_version=requirement.standard_version,
        disclosure_id=requirement.disclosure_id,
        requirement_id=requirement.requirement_id,
        requirement_text=requirement.requirement_text,
        keywords=requirement.keywords,
    )


@pytest.fixture
def repo_session():
    engine = make_test_engine()
    reset_database(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def seed_report(repo):
    repo.create_report(
        Report(
            report_id="report-1",
            original_filename="report.pdf",
            stored_path="backend/data/runtime/uploads/report.pdf",
            file_hash="hash-1",
            page_count=1,
        )
    )


def test_single_report_workflow_completes_without_model_calls(repo_session):
    repo = Repository(repo_session)
    seed_report(repo)
    workflow = SingleReportWorkflow(repo, FakeParser(), FakeAdapter(), DisclosureAgent())

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False)

    assert run.status is RunStatus.COMPLETED
    assert repo_session.scalar(select(AssessmentRecord).where(AssessmentRecord.run_id == run.run_id)).model_called is False
    event_types = repo_session.scalars(
        select(AuditEventRecord.event_type)
        .where(AuditEventRecord.run_id == run.run_id)
        .order_by(AuditEventRecord.audit_event_id)
    ).all()
    assert event_types == ["analysis_started", "parse_completed", "analysis_completed"]


def test_single_report_workflow_marks_run_failed_on_parser_error(repo_session):
    repo = Repository(repo_session)
    seed_report(repo)
    workflow = SingleReportWorkflow(repo, FailingParser(), FakeAdapter(), DisclosureAgent())

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False)

    assert run.status is RunStatus.FAILED
    assert "parse failed" in (run.error_message or "")
    assert repo_session.scalar(select(RecommendationRecord).where(RecommendationRecord.run_id == run.run_id)) is None


def test_single_report_workflow_attaches_report_index_candidate_pages(repo_session, tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "canonical_disclosure_id": "2-1",
                        "report_index_pdf_page": 71,
                        "report_index_report_page": 70,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    repo = Repository(repo_session)
    seed_report(repo)
    workflow = SingleReportWorkflow(
        repo,
        IndexParser(),
        FakeAdapter(),
        DisclosureAgent(),
        requirement_pack_path=pack_path,
    )

    run = workflow.run("report-1", Path("report.pdf"), "hash-1", confirm_llm=False)

    assert run.status is RunStatus.COMPLETED
    task = repo_session.scalar(select(DisclosureTaskRecord).where(DisclosureTaskRecord.run_id == run.run_id))
    assert task.keywords == ["legal", "name"]
    evidence = repo_session.scalar(select(EvidenceItemRecord).where(EvidenceItemRecord.run_id == run.run_id))
    assert evidence.source_page == 6
    assert evidence.source_pdf_page == 6
    assert evidence.source_report_page == 5
    assert evidence.evidence_metadata["retrieval_strategy"] == "index_page_bounded"
    assert evidence.evidence_metadata["candidate_pages"] == [6]
    assert evidence.evidence_metadata["candidate_pdf_pages"] == [6]
    assert evidence.evidence_metadata["candidate_report_pages"] == [5]
    assert evidence.evidence_metadata["index_page"] == 71
    assert evidence.evidence_metadata["source_pdf_page"] == 6
    assert evidence.evidence_metadata["source_report_page"] == 5


def test_single_report_workflow_supplements_candidate_pages_for_entity_attributes(tmp_path):
    pack_path = tmp_path / "gri_requirement_pack.json"
    pack_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "canonical_disclosure_id": "2-1",
                        "report_index_pdf_page": 71,
                        "report_index_report_page": 70,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    workflow = SingleReportWorkflow(
        None,
        FakeParser(),
        FakeAdapter(),
        DisclosureAgent(),
        requirement_pack_path=pack_path,
    )
    pages = [
        PageExtraction(report_id="report-1", page_number=1, text="远景能源有限公司 Envision Energy Co., Ltd."),
        PageExtraction(report_id="report-1", page_number=3, text="报告主体为远景能源有限公司。"),
        PageExtraction(report_id="report-1", page_number=6, text="关于远景能源"),
        PageExtraction(report_id="report-1", page_number=28, text="上海总部大楼持续推进绿色运营。"),
        PageExtraction(report_id="report-1", page_number=71, text="2-1 组织详细情况 关于远景能源 5"),
    ]
    from src.domain.models import DisclosureTask

    tasks = [
        DisclosureTask(
            task_id="task-2-1-a",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-1",
            requirement_id="GRI 2-1-a",
            requirement_text="report its legal name;",
            keywords=["有限公司"],
        ),
        DisclosureTask(
            task_id="task-2-1-c",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI 2",
            standard_version="2021",
            disclosure_id="GRI 2-1",
            requirement_id="GRI 2-1-c",
            requirement_text="report the location of its headquarters;",
            keywords=["总部"],
        ),
    ]

    enriched = workflow._attach_report_index_candidates(pages, tasks)

    assert enriched[0].candidate_pages == [1, 3, 6]
    assert enriched[0].candidate_pdf_pages == [1, 3, 6]
    assert enriched[0].candidate_report_pages == [None, 2, 5]
    assert enriched[0].candidate_page_source == "gri_report_index+requirement_supplement"
    assert enriched[1].candidate_pages == [6, 28]
    assert enriched[1].candidate_pdf_pages == [6, 28]
    assert enriched[1].candidate_report_pages == [5, 27]
    assert enriched[1].candidate_page_source == "gri_report_index+requirement_supplement"
