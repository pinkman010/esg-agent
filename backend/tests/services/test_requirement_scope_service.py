import importlib
from pathlib import Path

from src.domain.enums import AssessmentVerdict, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment
from src.standards.gri import GRIAdapter


class FakeRepository:
    def __init__(self, assessments, *, include_run=True):
        self.assessments = assessments
        self.include_run = include_run

    def latest_run_for_report(self, report_id):
        if not self.include_run:
            return None
        return AnalysisRun(
            run_id="run-scope",
            report_id=report_id,
            status=RunStatus.COMPLETED,
        )

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
    assert all(item["assessment_id"] is None for item in context)
    assert all(item["effective_verdict"] is None for item in context)
    assert all(item["review_priority"] is None for item in context)
    assert all(item["review_status"] is None for item in context)
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


def test_scope_service_rejects_run_assessment_count_mismatch():
    module = importlib.import_module("src.services.requirement_scope_service")
    adapter = _adapter()
    service = module.RequirementScopeService(
        FakeRepository(_assessments(adapter)[:-1]),
        adapter,
    )

    try:
        service.list_items("report-scope")
    except ValueError as exc:
        assert "499 independent assessments" in str(exc)
    else:
        raise AssertionError("scope mismatch should fail explicitly")
