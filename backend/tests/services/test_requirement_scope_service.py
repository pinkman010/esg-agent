import importlib
from pathlib import Path

from src.domain.enums import AssessmentVerdict, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment
from src.standards.gri import GRIAdapter


class FakeRepository:
    def __init__(
        self,
        assessments,
        *,
        include_run=True,
        failure_summary=None,
    ):
        self.assessments = assessments
        self.include_run = include_run
        self.run = AnalysisRun(
            run_id="run-scope",
            report_id="report-scope",
            status=RunStatus.COMPLETED,
            failure_summary=failure_summary or {},
        )

    def latest_run_for_report(self, report_id):
        if not self.include_run:
            return None
        assert report_id == self.run.report_id
        return self.run

    def get_run(self, run_id):
        return self.run if run_id == self.run.run_id else None

    def list_assessments_by_run(self, run_id):
        assert run_id == "run-scope"
        return self.assessments

    def latest_risks_for_assessments(self, assessment_ids):
        return {}

    def latest_snapshots_for_assessments(self, assessment_ids):
        return {}


def _adapter():
    backend_root = Path(__file__).resolve().parents[2]
    return GRIAdapter(
        backend_root / "data/manifests/gri_requirement_checklist_v3.json"
    )


def _assessments(adapter):
    return [
        DisclosureAssessment(
            assessment_id=f"assessment-{index}",
            run_id="run-scope",
            report_id="report-scope",
            standard_id=requirement.standard_id,
            standard_version=requirement.standard_version,
            disclosure_id=requirement.disclosure_id,
            requirement_id=requirement.requirement_id,
            verdict=AssessmentVerdict.UNKNOWN,
            rationale="待核实",
        )
        for index, requirement in enumerate(adapter.load_requirements(), start=1)
    ]


def test_scope_service_merges_499_assessments_into_577_standard_units():
    module = importlib.import_module("src.services.requirement_scope_service")
    adapter = _adapter()
    service = module.RequirementScopeService(
        FakeRepository(_assessments(adapter)),
        adapter,
    )

    items = service.list_items("report-scope")

    assert len(items) == 577
    assessed = [item for item in items if item["unit_status"] == "assessed"]
    context = [
        item for item in items if item["unit_status"] == "context_incorporated"
    ]
    assert len(assessed) == 499
    assert len(context) == 78
    assert all(item["assessment_id"] for item in assessed)
    assert all(item["effective_verdict"] == "unknown" for item in assessed)
    assert all(item["analysis_status"] == "succeeded" for item in assessed)
    assert all(item["source_run_id"] == "run-scope" for item in assessed)
    assert all(item["assessment_id"] is None for item in context)
    assert all(item["effective_verdict"] is None for item in context)
    assert all(item["analysis_status"] is None for item in context)
    assert all(item["source_run_id"] is None for item in context)
    assert all(item["review_priority"] is None for item in context)
    assert all(item["review_status"] is None for item in context)
    assert all(item["applicability_status"] is None for item in context)
    assert any(item["incorporated_into_requirement_ids"] for item in context)
    assert items[0]["requirement_id"] == "GRI 2-1-a"


def test_scope_service_without_run_returns_structure_without_fake_assessments():
    module = importlib.import_module("src.services.requirement_scope_service")
    adapter = _adapter()
    service = module.RequirementScopeService(
        FakeRepository([], include_run=False),
        adapter,
    )

    items = service.list_items("report-scope")

    assert len(items) == 577
    assert all(item["assessment_id"] is None for item in items)
    assert sum(item["analysis_status"] == "not_generated" for item in items) == 499
    assert sum(item["analysis_status"] is None for item in items) == 78


def test_scope_service_returns_complete_range_for_partial_run():
    module = importlib.import_module("src.services.requirement_scope_service")
    adapter = _adapter()
    assessments = _assessments(adapter)[:-1]
    failed_requirement_id = adapter.load_requirements()[-1].requirement_id
    service = module.RequirementScopeService(
        FakeRepository(
            assessments,
            failure_summary={
                "failed_requirement_ids": [failed_requirement_id],
            },
        ),
        adapter,
    )

    items = service.list_items("report-scope")

    assert len(items) == 577
    failed = next(
        item for item in items if item["requirement_id"] == failed_requirement_id
    )
    assert failed["unit_status"] == "assessed"
    assert failed["analysis_status"] == "failed"
    assert failed["failure_code"] == "assessment_failed"
    assert failed["failure_message"] == "该核查项分析失败，可通过失败重试恢复。"
    assert failed["assessment_id"] is None
    assert failed["effective_verdict"] is None
    assert failed["source_run_id"] is None
