import pytest

from src.db.repositories import Repository
from src.domain.enums import AssessmentVerdict, ReportStatus, ReviewOperation, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, Report
from src.services.review_service import ReviewService
from tests.database import make_test_engine, reset_database
from src.db.base import Base
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def service_context():
    engine = make_test_engine()
    reset_database(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = Repository(session)
    repo.create_report(Report(report_id="report-1", original_filename="report.pdf", stored_path="x", file_hash="hash-1"))
    repo.create_run(AnalysisRun(run_id="run-1", report_id="report-1", status=RunStatus.COMPLETED))
    repo.save_assessment(
        DisclosureAssessment(
            assessment_id="assessment-1",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 2-1",
            requirement_id="GRI 2-1-a",
            verdict=AssessmentVerdict.UNKNOWN,
            rationale="No evidence.",
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        )
    )
    try:
        yield ReviewService(repo), repo
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_review_service_appends_snapshots_without_mutating_system_assessment(service_context):
    service, repo = service_context
    first = service.record(
        "assessment-1",
        operation_type=ReviewOperation.APPROVE,
        reviewer_name="张三",
        reason_code="system_result_confirmed",
    )
    second = service.record(
        "assessment-1",
        operation_type=ReviewOperation.MODIFY,
        reviewer_name="张三",
        reason_code="verdict_corrected",
        reviewer_note="人工补充判断",
        reviewed_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
        expected_previous_snapshot_id=first.snapshot_id,
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert second.previous_snapshot_id == first.snapshot_id
    assert repo.list_assessments_by_run("run-1")[0].review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert repo.list_review_change_events(second.snapshot_id)[0].field_name == "reviewed_verdict"


def test_review_service_enforces_notes_and_optimistic_concurrency(service_context):
    service, _ = service_context
    with pytest.raises(ValueError, match="reviewer_note"):
        service.record(
            "assessment-1",
            operation_type=ReviewOperation.MODIFY,
            reviewer_name="张三",
            reason_code="verdict_corrected",
            reviewed_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
        )
    first = service.record(
        "assessment-1",
        operation_type=ReviewOperation.APPROVE,
        reviewer_name="张三",
        reason_code="system_result_confirmed",
    )
    with pytest.raises(RuntimeError, match="snapshot conflict"):
        service.record(
            "assessment-1",
            operation_type=ReviewOperation.APPROVE,
            reviewer_name="李四",
            reason_code="system_result_confirmed",
            expected_previous_snapshot_id="stale-snapshot",
        )
    assert first.sequence == 1


def test_review_service_advances_and_reopens_report_status(service_context):
    service, repo = service_context

    approved = service.record(
        "assessment-1",
        operation_type=ReviewOperation.APPROVE,
        reviewer_name="张三",
        reason_code="system_result_confirmed",
    )

    assert repo.get_report("report-1").status is ReportStatus.HIGH_RISK_REVIEW_COMPLETED

    service.record(
        "assessment-1",
        operation_type=ReviewOperation.REOPEN,
        reviewer_name="张三",
        reason_code="new_evidence_received",
        reviewer_note="收到新证据，重新开启复核。",
        expected_previous_snapshot_id=approved.snapshot_id,
    )

    assert repo.get_report("report-1").status is ReportStatus.REOPENED
