import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import AIAssessmentSuggestionRecord, DisclosureTaskRecord, DocumentChunkRecord, DocumentPageRecord, RecommendationRecord
from src.db.repositories import Repository
from src.domain.ai_models import AIAssessmentSuggestion
from src.domain.enums import (
    AISuggestionStatus,
    ApplicabilityStatus,
    AssessmentVerdict,
    EvidenceSourceMethod,
    EvidenceStatus,
    PageQualityFlag,
    ReportStatus,
    ReviewOperation,
    ReviewStatus,
    RiskLevel,
    RunStatus,
)
from src.domain.models import (
    AnalysisRun,
    AnalysisStageEvent,
    AssessmentRisk,
    DisclosureAssessment,
    DisclosureTask,
    DocumentChunk,
    EvidenceItem,
    PageExtraction,
    Recommendation,
    Report,
    ReviewDecision,
    ReviewSnapshot,
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


def test_repository_lists_and_confirms_report_metadata():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id="report-1",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-1",
                page_count=10,
                status=ReportStatus.UPLOADED,
                metadata_detected={"report_year": 2024},
            )
        )

        reports, total = repo.list_reports(page=1, page_size=10)
        assert total == 1
        assert reports[0].status == ReportStatus.UPLOADED
        assert repo.find_report_by_hash("hash-1").report_id == "report-1"

        confirmed = repo.confirm_report_metadata(
            "report-1",
            company_name="测试公司",
            report_year=2024,
            language="zh-CN",
        )

        assert confirmed.status == ReportStatus.READY_FOR_ANALYSIS
        assert confirmed.company_name == "测试公司"
        assert confirmed.metadata_confirmed_at is not None
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_repository_finds_latest_report_for_a_repeated_file_hash():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(Report(report_id="report-1", original_filename="first.pdf", stored_path="first.pdf", file_hash="same-hash"))
        time.sleep(0.01)
        repo.create_report(Report(report_id="report-2", original_filename="second.pdf", stored_path="second.pdf", file_hash="same-hash"))

        assert repo.find_report_by_hash("same-hash").report_id == "report-2"
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_repository_appends_analysis_stage_events_and_creates_retry_run():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(Report(report_id="report-1", original_filename="report.pdf", stored_path="x", file_hash="hash-1"))
        repo.create_run(
            AnalysisRun(
                run_id="run-1",
                report_id="report-1",
                status=RunStatus.PARTIALLY_COMPLETED,
                eligible_requirement_count=2,
                succeeded_requirement_count=1,
                failed_requirement_count=1,
                failure_summary={"failed_requirement_ids": ["GRI 2-1-b"]},
            )
        )
        repo.append_analysis_stage_event(
            AnalysisStageEvent(run_id="run-1", stage_code="pdf_parsing", status="running", completed_units=0, total_units=1)
        )
        repo.append_analysis_stage_event(
            AnalysisStageEvent(run_id="run-1", stage_code="pdf_parsing", status="completed", completed_units=1, total_units=1)
        )

        stages = repo.list_latest_analysis_stages("run-1")
        retry = repo.create_retry_run("run-1", reason="retry failed requirements")

        assert stages[0].status == "completed"
        assert retry.parent_run_id == "run-1"
        assert retry.failure_summary["retry_requirement_ids"] == ["GRI 2-1-b"]
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_repository_enforces_one_active_run_per_report_and_tracks_lifecycle_times():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id="report-active-run",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-active-run",
            )
        )

        pending = repo.create_run(
            AnalysisRun(
                run_id="run-pending",
                report_id="report-active-run",
                status=RunStatus.PENDING,
            )
        )
        assert repo.get_active_run_for_report("report-active-run").run_id == pending.run_id

        with pytest.raises(ValueError, match="active analysis run already exists"):
            repo.create_run(
                AnalysisRun(
                    run_id="run-concurrent",
                    report_id="report-active-run",
                    status=RunStatus.RUNNING,
                )
            )

        running = repo.update_run_status("run-pending", RunStatus.RUNNING)
        assert running.started_at is not None
        started_at = running.started_at
        time.sleep(0.01)
        assert repo.update_run_status("run-pending", RunStatus.RUNNING).started_at == started_at

        completed = repo.update_run_status("run-pending", RunStatus.COMPLETED)
        assert completed.completed_at is not None
        completed_at = completed.completed_at
        assert repo.get_active_run_for_report("report-active-run") is None

        time.sleep(0.01)
        terminal_update = repo.update_run_status("run-pending", RunStatus.FAILED)
        assert terminal_update.completed_at == completed_at

        next_run = repo.create_run(
            AnalysisRun(
                run_id="run-next",
                report_id="report-active-run",
                status=RunStatus.RUNNING,
            )
        )
        assert next_run.run_id == "run-next"
        assert repo.get_active_run_for_report("report-active-run").run_id == "run-next"

        index_names = {index["name"] for index in inspect(engine).get_indexes("analysis_runs")}
        assert "uq_analysis_runs_one_active_per_report" in index_names
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_repository_replaces_pages_and_chunks_for_same_report():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id="report-idempotent",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-idempotent",
                page_count=1,
            )
        )

        repo.save_pages_and_chunks(
            pages=[
                PageExtraction(
                    report_id="report-idempotent",
                    page_number=1,
                    text="first text",
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                )
            ],
            chunks=[
                DocumentChunk(
                    chunk_id="report-idempotent-p1-pdfplumber",
                    report_id="report-idempotent",
                    text="first text",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash="hash-idempotent",
                )
            ],
        )
        repo.save_pages_and_chunks(
            pages=[
                PageExtraction(
                    report_id="report-idempotent",
                    page_number=1,
                    text="updated text",
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                )
            ],
            chunks=[
                DocumentChunk(
                    chunk_id="report-idempotent-p1-pdfplumber",
                    report_id="report-idempotent",
                    text="updated text",
                    source_page=1,
                    source_method=EvidenceSourceMethod.PDFPLUMBER,
                    source_file_hash="hash-idempotent",
                )
            ],
        )

        page_count = session.scalar(
            select(func.count())
            .select_from(DocumentPageRecord)
            .where(DocumentPageRecord.report_id == "report-idempotent")
        )
        chunk_count = session.scalar(
            select(func.count())
            .select_from(DocumentChunkRecord)
            .where(DocumentChunkRecord.report_id == "report-idempotent")
        )
        saved_chunk = session.get(DocumentChunkRecord, "report-idempotent-p1-pdfplumber")

        assert page_count == 1
        assert chunk_count == 1
        assert saved_chunk.text == "updated text"
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_repository_rollback_recovers_after_page_chunk_commit_failure():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id="report-rollback",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-rollback",
            )
        )
        repo.create_run(
            AnalysisRun(
                run_id="run-rollback",
                report_id="report-rollback",
                status=RunStatus.PENDING,
            )
        )

        with pytest.raises(IntegrityError):
            repo.save_pages_and_chunks(
                pages=[],
                chunks=[
                    DocumentChunk(
                        chunk_id="invalid-foreign-key-chunk",
                        report_id="missing-report",
                        text="invalid",
                        source_page=1,
                        source_method=EvidenceSourceMethod.PDFPLUMBER,
                        source_file_hash="hash-missing",
                    )
                ],
            )

        repo.rollback()
        repo.create_audit_event("run-rollback", "analysis_failed", {"reason": "test"})
        failed_run = repo.update_run_status("run-rollback", RunStatus.FAILED, "test failure")

        assert repo.count_audit_events("run-rollback") == 1
        assert failed_run.status == RunStatus.FAILED
        assert failed_run.completed_at is not None
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


def test_repository_round_trips_risk_v2_1_dimensions_and_reviewed_applicability():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id="report-risk-v2-1",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-risk-v2-1",
            )
        )
        repo.create_run(
            AnalysisRun(
                run_id="run-risk-v2-1",
                report_id="report-risk-v2-1",
                risk_rule_version="risk-v2.1",
            )
        )
        assessment = DisclosureAssessment(
            assessment_id="assessment-risk-v2-1",
            run_id="run-risk-v2-1",
            report_id="report-risk-v2-1",
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 2-1",
            requirement_id="GRI 2-1-a",
            verdict=AssessmentVerdict.UNKNOWN,
            rationale="未发现有效证据。",
            evidence=[],
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        )
        repo.save_assessment(assessment)

        saved_risk = repo.save_assessment_risk(
            AssessmentRisk(
                risk_id="risk-v2-1",
                assessment_id=assessment.assessment_id,
                risk_level=RiskLevel.LOW,
                reason_codes=["unknown_verdict", "no_valid_evidence"],
                risk_rule_version="risk-v2.1",
                trigger_event="analysis_completed",
                evidence_status=EvidenceStatus.MISSING,
                applicability_status=ApplicabilityStatus.UNDETERMINED,
            )
        )
        saved_snapshot = repo.save_review_snapshot(
            ReviewSnapshot(
                snapshot_id="snapshot-risk-v2-1",
                assessment_id=assessment.assessment_id,
                run_id=assessment.run_id,
                sequence=1,
                operation_type=ReviewOperation.MODIFY,
                reviewer_name="张三",
                reason_code="applicability_reviewed",
                reviewed_applicability_status=ApplicabilityStatus.APPLICABLE,
            ),
            [],
        )

        assert saved_risk.evidence_status is EvidenceStatus.MISSING
        assert saved_risk.applicability_status is ApplicabilityStatus.UNDETERMINED
        assert saved_snapshot.reviewed_applicability_status is ApplicabilityStatus.APPLICABLE
        latest_risk = repo.latest_risks_for_assessments([assessment.assessment_id])[
            assessment.assessment_id
        ]
        latest_snapshot = repo.latest_review_snapshot(assessment.assessment_id)
        assert latest_risk.evidence_status is EvidenceStatus.MISSING
        assert latest_risk.applicability_status is ApplicabilityStatus.UNDETERMINED
        assert latest_snapshot.reviewed_applicability_status is ApplicabilityStatus.APPLICABLE

        risk_columns = {column["name"] for column in inspect(engine).get_columns("assessment_risks")}
        snapshot_columns = {column["name"] for column in inspect(engine).get_columns("review_snapshots")}
        assert {"evidence_status", "applicability_status"}.issubset(risk_columns)
        assert "reviewed_applicability_status" in snapshot_columns
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_repository_appends_and_queries_ai_suggestions_without_overwriting_history():
    engine, session = make_session()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id="report-ai",
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash="hash-ai",
            )
        )
        repo.create_run(AnalysisRun(run_id="run-ai", report_id="report-ai"))
        repo.save_assessment(
            DisclosureAssessment(
                assessment_id="assessment-ai",
                run_id="run-ai",
                report_id="report-ai",
                standard_id="GRI",
                standard_version="2021",
                disclosure_id="GRI 2-1",
                requirement_id="GRI 2-1-a",
                verdict=AssessmentVerdict.UNKNOWN,
                rationale="未发现充分证据。",
                evidence=[],
            )
        )
        first = AIAssessmentSuggestion(
            suggestion_id="suggestion-1",
            assessment_id="assessment-ai",
            run_id="run-ai",
            status=AISuggestionStatus.SUCCEEDED,
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_version="prompt-v1",
            input_hash="a" * 64,
            suggested_verdict=AssessmentVerdict.UNKNOWN,
            rationale_zh="第一版建议。",
            created_at=datetime.now(UTC),
        )
        second = AIAssessmentSuggestion(
            suggestion_id="suggestion-2",
            assessment_id="assessment-ai",
            run_id="run-ai",
            status=AISuggestionStatus.SUCCEEDED,
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_version="prompt-v2",
            input_hash="b" * 64,
            suggested_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
            rationale_zh="第二版建议。",
            missing_items_zh=["范围"],
            created_at=first.created_at + timedelta(seconds=1),
        )

        repo.append_ai_suggestion(first)
        repo.append_ai_suggestion(second)

        latest = repo.get_latest_ai_suggestion("assessment-ai")
        history = repo.list_ai_suggestions_for_run("run-ai")
        assert latest.suggestion_id == "suggestion-2"
        assert [item.suggestion_id for item in history] == ["suggestion-1", "suggestion-2"]
        assert session.scalar(
            select(func.count()).select_from(AIAssessmentSuggestionRecord)
        ) == 2
        with pytest.raises(IntegrityError):
            repo.append_ai_suggestion(first)
    finally:
        session.rollback()
        session.close()
        reset_database(engine)
        engine.dispose()
