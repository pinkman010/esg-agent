import asyncio

import pytest
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.repositories import Repository
from src.domain.enums import ReportStatus, RunStatus
from src.domain.models import AnalysisRun, Report
from src.services import analysis_job
from tests.database import make_test_engine, reset_database


INTERRUPTED_REASON = "分析服务重启，任务已中断"


@pytest.fixture
def job_session_factory(monkeypatch):
    engine = make_test_engine()
    reset_database(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(analysis_job, "SessionLocal", factory)
    try:
        yield factory
    finally:
        reset_database(engine)
        engine.dispose()


def _create_report_and_run(
    factory,
    *,
    report_id: str,
    run_id: str,
    report_status: ReportStatus,
    run_status: RunStatus,
    error_message: str | None = None,
) -> None:
    session = factory()
    try:
        repo = Repository(session)
        repo.create_report(
            Report(
                report_id=report_id,
                original_filename="report.pdf",
                stored_path="backend/data/runtime/uploads/report.pdf",
                file_hash=f"hash-{report_id}",
                status=report_status,
            )
        )
        repo.create_run(
            AnalysisRun(
                run_id=run_id,
                report_id=report_id,
                status=run_status,
                error_message=error_message,
            )
        )
    finally:
        session.close()


def test_execute_analysis_job_persists_terminal_failure_in_its_own_session(
    job_session_factory,
    monkeypatch,
):
    _create_report_and_run(
        job_session_factory,
        report_id="report-job",
        run_id="run-job",
        report_status=ReportStatus.ANALYZING,
        run_status=RunStatus.RUNNING,
    )

    def fail_analysis(*args, **kwargs):
        raise RuntimeError("job exploded")

    monkeypatch.setattr(analysis_job, "execute_analysis", fail_analysis)

    analysis_job.execute_analysis_job(
        report_id="report-job",
        run_id="run-job",
        confirm_llm=False,
    )

    session = job_session_factory()
    try:
        repo = Repository(session)
        run = repo.get_run("run-job")
        report = repo.get_report("report-job")
        result_stage = next(
            stage
            for stage in repo.list_latest_analysis_stages("run-job")
            if stage.stage_code == "result_summary"
        )

        assert run.status is RunStatus.FAILED
        assert run.error_message == "job exploded"
        assert run.completed_at is not None
        assert report.status is ReportStatus.ANALYSIS_FAILED
        assert result_stage.status == "failed"
        assert result_stage.error_summary == "job exploded"
        assert repo.count_audit_events("run-job") == 1
    finally:
        session.close()


def test_recover_interrupted_analysis_runs_only_fails_pending_and_running(
    job_session_factory,
):
    cases = [
        ("pending", ReportStatus.READY_FOR_ANALYSIS, RunStatus.PENDING, None),
        ("running", ReportStatus.ANALYZING, RunStatus.RUNNING, None),
        ("completed", ReportStatus.ANALYSIS_COMPLETED, RunStatus.COMPLETED, "completed-original"),
        ("failed", ReportStatus.ANALYSIS_FAILED, RunStatus.FAILED, "failed-original"),
    ]
    for name, report_status, run_status, error_message in cases:
        _create_report_and_run(
            job_session_factory,
            report_id=f"report-{name}",
            run_id=f"run-{name}",
            report_status=report_status,
            run_status=run_status,
            error_message=error_message,
        )

    recovered = analysis_job.recover_interrupted_analysis_runs()

    session = job_session_factory()
    try:
        repo = Repository(session)
        for name in ("pending", "running"):
            run = repo.get_run(f"run-{name}")
            report = repo.get_report(f"report-{name}")
            stage = next(
                stage
                for stage in repo.list_latest_analysis_stages(run.run_id)
                if stage.stage_code == "result_summary"
            )
            assert run.status is RunStatus.FAILED
            assert run.error_message == INTERRUPTED_REASON
            assert report.status is ReportStatus.ANALYSIS_FAILED
            assert stage.status == "failed"
            assert stage.error_summary == INTERRUPTED_REASON

        assert repo.get_run("run-completed").status is RunStatus.COMPLETED
        assert repo.get_run("run-completed").error_message == "completed-original"
        assert repo.get_report("report-completed").status is ReportStatus.ANALYSIS_COMPLETED
        assert repo.get_run("run-failed").status is RunStatus.FAILED
        assert repo.get_run("run-failed").error_message == "failed-original"
        assert repo.get_report("report-failed").status is ReportStatus.ANALYSIS_FAILED
        assert recovered == 2
    finally:
        session.close()


def test_create_app_lifespan_recovers_interrupted_runs(monkeypatch):
    from src import main

    calls = []
    monkeypatch.setattr(main, "recover_interrupted_analysis_runs", lambda: calls.append("recovered"))
    app = main.create_app()

    async def enter_lifespan():
        async with app.router.lifespan_context(app):
            assert calls == ["recovered"]

    asyncio.run(enter_lifespan())
    assert calls == ["recovered"]
