from __future__ import annotations

import importlib

import pytest

from src.domain.enums import AssessmentVerdict, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment


class FakeRepository:
    def __init__(
        self,
        *,
        latest_run: AnalysisRun | None,
        runs: list[AnalysisRun] | None = None,
        assessments_by_run: dict[str, list[DisclosureAssessment]] | None = None,
    ):
        self.latest_run = latest_run
        self.runs = {
            run.run_id: run for run in (runs or ([latest_run] if latest_run else []))
        }
        self.assessments_by_run = assessments_by_run or {}

    def latest_run_for_report(self, report_id: str) -> AnalysisRun | None:
        if self.latest_run is None or self.latest_run.report_id != report_id:
            return None
        return self.latest_run

    def get_run(self, run_id: str) -> AnalysisRun | None:
        return self.runs.get(run_id)

    def list_assessments_by_run(self, run_id: str) -> list[DisclosureAssessment]:
        return list(self.assessments_by_run.get(run_id, []))


def _run(
    run_id: str,
    *,
    report_id: str = "report-1",
    parent_run_id: str | None = None,
    failed_ids: list[str] | None = None,
) -> AnalysisRun:
    return AnalysisRun(
        run_id=run_id,
        report_id=report_id,
        status=RunStatus.PARTIALLY_COMPLETED,
        parent_run_id=parent_run_id,
        failure_summary={"failed_requirement_ids": failed_ids or []},
    )


def _assessment(
    requirement_id: str,
    *,
    run_id: str,
    report_id: str = "report-1",
    suffix: str = "",
) -> DisclosureAssessment:
    return DisclosureAssessment(
        assessment_id=f"assessment-{run_id}-{requirement_id}{suffix}",
        run_id=run_id,
        report_id=report_id,
        standard_id="GRI",
        standard_version="2021",
        disclosure_id=requirement_id,
        requirement_id=requirement_id,
        verdict=AssessmentVerdict.UNKNOWN,
        rationale="待核实",
    )


def _service(repository: FakeRepository, *, max_depth: int = 32):
    module = importlib.import_module("src.services.effective_run_view_service")
    return module.EffectiveRunViewService(repository, max_depth=max_depth)


def test_effective_view_returns_all_assessments_from_complete_latest_run():
    latest = _run("run-latest")
    repository = FakeRepository(
        latest_run=latest,
        assessments_by_run={
            latest.run_id: [
                _assessment("GRI-A", run_id=latest.run_id),
                _assessment("GRI-B", run_id=latest.run_id),
            ]
        },
    )

    view = _service(repository).build(
        report_id="report-1",
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert view.latest_run == latest
    assert set(view.assessments_by_requirement) == {"GRI-A", "GRI-B"}
    assert view.assessments_by_requirement["GRI-A"].source_run_id == "run-latest"
    assert view.failed_requirement_ids == frozenset()
    assert view.not_generated_requirement_ids == frozenset()


def test_effective_view_prefers_retry_assessment_and_keeps_parent_successes():
    parent = _run("run-parent", failed_ids=["GRI-B"])
    retry = _run(
        "run-retry",
        parent_run_id=parent.run_id,
    )
    repository = FakeRepository(
        latest_run=retry,
        runs=[parent, retry],
        assessments_by_run={
            parent.run_id: [_assessment("GRI-A", run_id=parent.run_id)],
            retry.run_id: [_assessment("GRI-B", run_id=retry.run_id)],
        },
    )

    view = _service(repository).build(
        report_id="report-1",
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert view.assessments_by_requirement["GRI-A"].source_run_id == "run-parent"
    assert view.assessments_by_requirement["GRI-B"].source_run_id == "run-retry"
    assert view.failed_requirement_ids == frozenset()
    assert view.not_generated_requirement_ids == frozenset()
    assert _service(repository).lineage_contains_eligible_count(
        latest_run=retry,
        eligible_count=499,
    ) is False


def test_effective_view_detects_scope_count_declared_by_parent_run():
    parent = _run("run-parent")
    parent.eligible_requirement_count = 499
    retry = _run("run-retry", parent_run_id=parent.run_id)
    retry.eligible_requirement_count = 1
    repository = FakeRepository(latest_run=retry, runs=[parent, retry])

    assert _service(repository).lineage_contains_eligible_count(
        latest_run=retry,
        eligible_count=499,
    ) is True


def test_effective_view_marks_retry_failure_without_discarding_parent_successes():
    parent = _run("run-parent", failed_ids=["GRI-B"])
    retry = _run(
        "run-retry",
        parent_run_id=parent.run_id,
        failed_ids=["GRI-B"],
    )
    repository = FakeRepository(
        latest_run=retry,
        runs=[parent, retry],
        assessments_by_run={
            parent.run_id: [_assessment("GRI-A", run_id=parent.run_id)],
            retry.run_id: [],
        },
    )

    view = _service(repository).build(
        report_id="report-1",
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert set(view.assessments_by_requirement) == {"GRI-A"}
    assert view.failed_requirement_ids == frozenset({"GRI-B"})
    assert view.not_generated_requirement_ids == frozenset()


def test_effective_view_distinguishes_never_generated_requirements():
    latest = _run("run-latest")
    repository = FakeRepository(
        latest_run=latest,
        assessments_by_run={
            latest.run_id: [_assessment("GRI-A", run_id=latest.run_id)]
        },
    )

    view = _service(repository).build(
        report_id="report-1",
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert view.failed_requirement_ids == frozenset()
    assert view.not_generated_requirement_ids == frozenset({"GRI-B"})


def test_effective_view_without_a_run_marks_independent_items_not_generated():
    view = _service(FakeRepository(latest_run=None)).build(
        report_id="report-1",
        independent_requirement_ids={"GRI-A", "GRI-B"},
    )

    assert view.latest_run is None
    assert view.assessments_by_requirement == {}
    assert view.failed_requirement_ids == frozenset()
    assert view.not_generated_requirement_ids == frozenset({"GRI-A", "GRI-B"})


def test_effective_view_ignores_out_of_scope_assessments_and_failure_ids():
    latest = _run("run-latest", failed_ids=["GRI-OUTSIDE"])
    repository = FakeRepository(
        latest_run=latest,
        assessments_by_run={
            latest.run_id: [
                _assessment("GRI-A", run_id=latest.run_id),
                _assessment("GRI-OUTSIDE", run_id=latest.run_id),
            ]
        },
    )

    view = _service(repository).build(
        report_id="report-1",
        independent_requirement_ids={"GRI-A"},
    )

    assert set(view.assessments_by_requirement) == {"GRI-A"}
    assert view.failed_requirement_ids == frozenset()
    assert view.not_generated_requirement_ids == frozenset()


def test_effective_view_rejects_duplicate_requirement_within_one_run():
    latest = _run("run-latest")
    duplicate = [
        _assessment("GRI-A", run_id=latest.run_id, suffix="-1"),
        _assessment("GRI-A", run_id=latest.run_id, suffix="-2"),
    ]
    repository = FakeRepository(
        latest_run=latest,
        assessments_by_run={latest.run_id: duplicate},
    )

    with pytest.raises(ValueError, match="duplicate assessment"):
        _service(repository).build(
            report_id="report-1",
            independent_requirement_ids={"GRI-A"},
        )


def test_effective_view_rejects_lineage_cycle():
    first = _run("run-first", parent_run_id="run-second")
    second = _run("run-second", parent_run_id="run-first")
    repository = FakeRepository(latest_run=first, runs=[first, second])

    with pytest.raises(ValueError, match="cycle"):
        _service(repository).build(
            report_id="report-1",
            independent_requirement_ids={"GRI-A"},
        )


def test_effective_view_rejects_lineage_beyond_depth_limit():
    parent = _run("run-parent")
    latest = _run("run-latest", parent_run_id=parent.run_id)
    repository = FakeRepository(latest_run=latest, runs=[latest, parent])

    with pytest.raises(ValueError, match="depth"):
        _service(repository, max_depth=1).build(
            report_id="report-1",
            independent_requirement_ids={"GRI-A"},
        )


def test_effective_view_rejects_parent_run_from_another_report():
    parent = _run("run-parent", report_id="report-2")
    latest = _run("run-latest", parent_run_id=parent.run_id)
    repository = FakeRepository(latest_run=latest, runs=[latest, parent])

    with pytest.raises(ValueError, match="another report"):
        _service(repository).build(
            report_id="report-1",
            independent_requirement_ids={"GRI-A"},
        )
