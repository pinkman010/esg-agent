from src.domain.enums import AssessmentVerdict, ReportStatus, RunStatus
from src.config.settings import Settings
from src.domain.models import AnalysisRun, DisclosureAssessment, Report
from src.services import analysis_runner


class FakeRepository:
    def __init__(self, latest_run, runs, assessments_by_run):
        self.latest_run = latest_run
        self.runs = {run.run_id: run for run in runs}
        self.assessments_by_run = assessments_by_run

    def latest_run_for_report(self, report_id):
        assert self.latest_run.report_id == report_id
        return self.latest_run

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def list_assessments_by_run(self, run_id):
        return list(self.assessments_by_run.get(run_id, []))


def _assessment(requirement_id, run_id):
    return DisclosureAssessment(
        assessment_id=f"assessment-{run_id}-{requirement_id}",
        run_id=run_id,
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id=requirement_id,
        requirement_id=requirement_id,
        verdict=AssessmentVerdict.UNKNOWN,
        rationale="待核实",
    )


def _lineage(*, retry_failed):
    parent = AnalysisRun(
        run_id="run-parent",
        report_id="report-1",
        status=RunStatus.PARTIALLY_COMPLETED,
        eligible_requirement_count=499,
        succeeded_requirement_count=1,
        failed_requirement_count=1,
        failure_summary={"failed_requirement_ids": ["GRI-B"]},
    )
    retry = AnalysisRun(
        run_id="run-retry",
        report_id="report-1",
        status=RunStatus.FAILED if retry_failed else RunStatus.COMPLETED,
        parent_run_id=parent.run_id,
        eligible_requirement_count=1,
        succeeded_requirement_count=0 if retry_failed else 1,
        failed_requirement_count=1 if retry_failed else 0,
        failure_summary={
            "retry_requirement_ids": ["GRI-B"],
            "failed_requirement_ids": ["GRI-B"] if retry_failed else [],
        },
    )
    assessments = {
        parent.run_id: [_assessment("GRI-A", parent.run_id)],
        retry.run_id: (
            [] if retry_failed else [_assessment("GRI-B", retry.run_id)]
        ),
    }
    return retry, FakeRepository(retry, [parent, retry], assessments)


def _resolve(*args, **kwargs):
    assert hasattr(analysis_runner, "resolve_effective_report_status")
    return analysis_runner.resolve_effective_report_status(*args, **kwargs)


def test_retry_failure_keeps_report_partially_completed_when_parent_has_results():
    retry, repository = _lineage(retry_failed=True)

    status = _resolve(
        repository,
        report_id="report-1",
        run_result=retry,
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert status is ReportStatus.PARTIALLY_COMPLETED


def test_retry_success_completes_report_when_effective_scope_has_all_results():
    retry, repository = _lineage(retry_failed=False)

    status = _resolve(
        repository,
        report_id="report-1",
        run_result=retry,
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert status is ReportStatus.ANALYSIS_COMPLETED


def test_legacy_run_status_mapping_remains_unchanged():
    run = AnalysisRun(
        run_id="run-legacy",
        report_id="report-1",
        status=RunStatus.FAILED,
        eligible_requirement_count=3,
    )
    repository = FakeRepository(run, [run], {run.run_id: []})

    status = _resolve(
        repository,
        report_id="report-1",
        run_result=run,
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert status is ReportStatus.ANALYSIS_FAILED


def test_execute_analysis_resolves_goldwind_profile_and_audits_selection(
    monkeypatch,
):
    captured: dict[str, object] = {}

    class FakeWorkflow:
        def __init__(self, repository, *args, report_profile_path=None, **kwargs):
            captured["report_profile_path"] = report_profile_path

        def run(self, report_id, pdf_path, source_file_hash, **kwargs):
            return AnalysisRun(
                run_id=kwargs["run_id"],
                report_id=report_id,
                status=RunStatus.COMPLETED,
                eligible_requirement_count=1,
                succeeded_requirement_count=1,
            )

    class ExecuteRepository:
        def __init__(self):
            self.latest_run = None
            self.audit_events = []
            self.report_status = None

        def create_audit_event(self, run_id, event_type, payload):
            self.audit_events.append((run_id, event_type, payload))

        def latest_run_for_report(self, report_id):
            return self.latest_run

        def update_report_status(self, report_id, status):
            self.report_status = status

    monkeypatch.setattr(analysis_runner, "SingleReportWorkflow", FakeWorkflow)
    repository = ExecuteRepository()
    report = Report(
        report_id="report-goldwind",
        original_filename="Goldwind 2024-zh.pdf",
        stored_path="data/reports/Goldwind 2024-zh.pdf",
        file_hash=(
            "f712694a6c05c599f3a272f314aa749be393f9007d92bc1fa6fd11bac5ad0119"
        ),
        page_count=52,
    )

    result = analysis_runner.execute_analysis(
        repository,
        report,
        Settings(app_env="test"),
        run_id="run-goldwind",
        confirm_llm=False,
    )

    assert result.status is RunStatus.COMPLETED
    assert captured["report_profile_path"] == (
        analysis_runner.DATA_ROOT
        / "reports"
        / "profiles"
        / "goldwind_2024.json"
    )
    assert repository.audit_events == [
        (
            "run-goldwind",
            "report_profile_resolved",
            {
                "report_id": "report-goldwind",
                "matched": True,
                "profile_id": "goldwind_2024",
            },
        )
    ]
