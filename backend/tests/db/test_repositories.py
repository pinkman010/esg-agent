from sqlalchemy import inspect, select
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import DisclosureTaskRecord, DocumentChunkRecord, DocumentPageRecord, RecommendationRecord
from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus, RunStatus
from src.domain.models import (
    AnalysisRun,
    DisclosureAssessment,
    DisclosureTask,
    DocumentChunk,
    EvidenceItem,
    PageExtraction,
    Recommendation,
    Report,
    ReviewDecision,
)
from tests.database import make_test_engine, reset_database


def make_session():
    engine = make_test_engine()
    reset_database(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, SessionLocal()


def test_required_tables_are_declared():
    engine, session = make_session()
    try:
        table_names = set(inspect(engine).get_table_names())

        assert {
            "reports",
            "analysis_runs",
            "document_pages",
            "document_chunks",
            "standard_requirements",
            "disclosure_tasks",
            "assessments",
            "evidence_items",
            "recommendations",
            "review_decisions",
            "audit_events",
        }.issubset(table_names)
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_repository_persists_report_run_assessment_evidence_and_review():
    engine, session = make_session()
    try:
        repo = Repository(session)

        report = repo.create_report(
            Report(
                report_id="report-1",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-1",
                page_count=10,
            )
        )
        assert report.report_id == "report-1"
        assert repo.get_report("report-1").file_hash == "hash-1"

        repo.create_run(
            AnalysisRun(
                run_id="run-1",
                report_id="report-1",
                status=RunStatus.PENDING,
                confirm_llm=False,
            )
        )
        repo.update_run_status("run-1", RunStatus.RUNNING)
        assert repo.list_runs()[0].status == RunStatus.RUNNING

        assessment = DisclosureAssessment(
            assessment_id="assessment-1",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 302",
            requirement_id="GRI 302-1-a",
            verdict=AssessmentVerdict.DISCLOSED,
            rationale="Evidence addresses the requirement.",
            evidence=[
                EvidenceItem(
                    evidence_id="evidence-1",
                    run_id="run-1",
                    report_id="report-1",
                    source_text="Total energy consumption is disclosed.",
                    source_page=12,
                    source_pdf_page=12,
                    source_report_page=11,
                    source_file_hash="hash-1",
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    quality_flags=[PageQualityFlag.SHORT_TEXT, PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED],
                    needs_ocr_or_vlm=True,
                    requires_ocr=True,
                    requires_vlm=False,
                    ocr_or_vlm_reason="assurance_page_text_too_short",
                )
            ],
            model_called=False,
            review_status=ReviewStatus.NOT_REQUIRED,
        )
        repo.save_assessment(assessment)
        repo.save_evidence_item("assessment-1", assessment.evidence[0])

        assessments = repo.list_assessments_by_run("run-1")
        assert len(assessments) == 1
        assert assessments[0].requirement_id == "GRI 302-1-a"
        saved_evidence = assessments[0].evidence[0]
        assert saved_evidence.source_page == 12
        assert saved_evidence.source_pdf_page == 12
        assert saved_evidence.source_report_page == 11
        assert saved_evidence.requires_ocr is True
        assert saved_evidence.requires_vlm is False
        assert saved_evidence.needs_ocr_or_vlm is True
        assert saved_evidence.ocr_or_vlm_reason == "assurance_page_text_too_short"
        assert saved_evidence.evidence_preview == "Total energy consumption is disclosed."
        assert saved_evidence.quality_flags == [PageQualityFlag.SHORT_TEXT, PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED]

        decision = repo.save_review_decision(
            ReviewDecision(
                decision_id="decision-1",
                run_id="run-1",
                assessment_id="assessment-1",
                review_status=ReviewStatus.APPROVED,
                reviewer_note="Checked evidence page.",
            )
        )
        assert decision.review_status == ReviewStatus.APPROVED

        repo.create_audit_event("run-1", "review_decision_saved", {"decision_id": "decision-1"})
        assert repo.count_audit_events("run-1") == 1
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()

def test_repository_saves_pages_chunks_tasks_and_recommendations():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id="report-2",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-2",
                page_count=1,
            )
        )
        repo.create_run(AnalysisRun(run_id="run-2", report_id="report-2"))

        repo.save_pages_and_chunks(
            pages=[
                PageExtraction(
                    report_id="report-2",
                    page_number=1,
                    text="Energy disclosure page",
                    image_count=0,
                    table_count=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                )
            ],
            chunks=[
                DocumentChunk(
                    chunk_id="chunk-1",
                    report_id="report-2",
                    text="Energy disclosure page",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash="hash-2",
                    embedding_status="not_started",
                )
            ],
        )
        assert session.scalar(select(DocumentPageRecord).where(DocumentPageRecord.report_id == "report-2")).page_number == 1
        assert session.scalar(select(DocumentChunkRecord).where(DocumentChunkRecord.chunk_id == "chunk-1")).embedding_status == "not_started"

        task = repo.save_disclosure_task(
            DisclosureTask(
                task_id="task-1",
                run_id="run-2",
                report_id="report-2",
                standard_id="GRI",
                standard_version="2021",
                disclosure_id="GRI 302",
                requirement_id="GRI 302-1-a",
                requirement_text="Disclose energy consumption.",
                keywords=["energy"],
            )
        )
        assert task.task_id == "task-1"
        assert session.scalar(select(DisclosureTaskRecord).where(DisclosureTaskRecord.task_id == "task-1")).keywords == ["energy"]

        recommendation = repo.save_recommendation(
            Recommendation(
                recommendation_id="recommendation-1",
                run_id="run-2",
                report_id="report-2",
                disclosure_id="GRI 302",
                requirement_id="GRI 302-1-a",
                recommendation_text="Add quantitative energy consumption disclosure.",
            )
        )
        assert recommendation.recommendation_id == "recommendation-1"
        assert session.scalar(select(RecommendationRecord).where(RecommendationRecord.recommendation_id == "recommendation-1")).requirement_id == "GRI 302-1-a"
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()
