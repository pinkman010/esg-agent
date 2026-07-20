import csv
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.repositories import Repository
from src.domain.enums import (
    AssessmentVerdict,
    EvidenceSourceMethod,
    ReportStatus,
    ReviewStatus,
    RiskLevel,
    RunStatus,
)
from src.domain.models import AnalysisRun, AssessmentRisk, DisclosureAssessment, EvidenceItem, Report
from tests.database import make_test_engine, reset_database


def _simulation_api():
    try:
        from src.tools.simulate_risk_v2 import (
            SimulationBaseline,
            SimulationBaselineMismatch,
            database_fingerprint,
            run_read_only_simulation,
            write_simulation_outputs,
        )
    except ImportError as exc:
        pytest.fail(f"risk-v2 simulation API is not implemented: {exc}")
    return {
        "SimulationBaseline": SimulationBaseline,
        "SimulationBaselineMismatch": SimulationBaselineMismatch,
        "database_fingerprint": database_fingerprint,
        "run_read_only_simulation": run_read_only_simulation,
        "write_simulation_outputs": write_simulation_outputs,
    }


def _evidence(assessment_id: str, evidence_type: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"evidence-{assessment_id}",
        run_id="run-1",
        report_id="report-1",
        source_text=f"Evidence for {assessment_id}",
        source_page=1,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        metadata={"evidence_type": evidence_type},
    )


def _assessment(
    assessment_id: str,
    requirement_id: str,
    verdict: AssessmentVerdict,
    evidence_type: str | None,
) -> DisclosureAssessment:
    evidence = [] if evidence_type is None else [_evidence(assessment_id, evidence_type)]
    return DisclosureAssessment(
        assessment_id=assessment_id,
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id=requirement_id,
        verdict=verdict,
        rationale=f"Rationale for {requirement_id}",
        evidence=evidence,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
    )


def _seed_simulation_database():
    engine = make_test_engine()
    reset_database(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    repo = Repository(session)
    repo.create_report(
        Report(
            report_id="report-1",
            original_filename="Envision Energy 2024-zh.pdf",
            stored_path="backend/data/runtime/demo/uploads/report.pdf",
            file_hash="hash-1",
            status=ReportStatus.ANALYSIS_COMPLETED,
        )
    )
    repo.create_run(
        AnalysisRun(
            run_id="run-1",
            report_id="report-1",
            status=RunStatus.COMPLETED,
            eligible_requirement_count=4,
            succeeded_requirement_count=4,
            risk_rule_version="risk-v1",
        )
    )
    cases = [
        (
            _assessment("assessment-1", "GRI 2-1-a", AssessmentVerdict.UNKNOWN, None),
            RiskLevel.HIGH,
            ["unknown_verdict", "no_valid_evidence"],
        ),
        (
            _assessment(
                "assessment-2",
                "GRI 2-1-b",
                AssessmentVerdict.PARTIALLY_DISCLOSED,
                "substantive",
            ),
            RiskLevel.MEDIUM,
            ["partial_disclosure"],
        ),
        (
            _assessment("assessment-3", "GRI 2-1-c", AssessmentVerdict.DISCLOSED, "substantive"),
            RiskLevel.LOW,
            ["direct_disclosure_evidence"],
        ),
        (
            _assessment("assessment-4", "GRI 2-1-d", AssessmentVerdict.DISCLOSED, "omission_note"),
            RiskLevel.HIGH,
            ["non_substantive_evidence_only"],
        ),
    ]
    for index, (assessment, risk_level, reason_codes) in enumerate(cases, start=1):
        repo.save_assessment(assessment)
        for evidence in assessment.evidence:
            repo.save_evidence_item(assessment.assessment_id, evidence)
        repo.save_assessment_risk(
            AssessmentRisk(
                risk_id=f"risk-{index}",
                assessment_id=assessment.assessment_id,
                risk_level=risk_level,
                reason_codes=reason_codes,
                risk_rule_version="risk-v1",
                trigger_event="analysis_completed",
            )
        )
    session.close()
    return engine, SessionLocal


def _baseline(api, *, high_count=2):
    return api["SimulationBaseline"](
        eligible_assessment_count=4,
        risk_v1_high_count=high_count,
        unknown_high_count=1,
    )


def test_read_only_simulation_preserves_database_and_builds_expected_distribution():
    api = _simulation_api()
    engine, SessionLocal = _seed_simulation_database()
    session = SessionLocal()
    try:
        before = api["database_fingerprint"](session, "report-1")

        result = api["run_read_only_simulation"](
            session,
            run_id="run-1",
            baseline=_baseline(api),
        )

        after = api["database_fingerprint"](session, "report-1")
        assert after == before
        assert result.old_priority_counts == {"high": 2, "medium": 1, "low": 1}
        assert result.new_priority_counts == {"high": 1, "low": 3}
        assert result.transition_counts["high->low"] == 1
        assert result.transition_counts["medium->low"] == 1
        assert result.transition_counts["high->high"] == 1
        assert result.applicability_counts == {"applicable": 3, "undetermined": 1}
        assert result.formal_output_gate == {
            "old_unresolved_high": 2,
            "new_unresolved_high": 1,
            "changed": True,
        }
        high_records = [record for record in result.records if record.new_review_priority == "high"]
        assert [record.requirement_id for record in high_records] == ["GRI 2-1-d"]
        assert "sufficiency_conflict" in high_records[0].new_reason_codes
        assert all(record.new_reason_codes != ("unknown_verdict",) for record in high_records)
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_simulation_rejects_mismatched_baseline_without_outputs(tmp_path: Path):
    api = _simulation_api()
    engine, SessionLocal = _seed_simulation_database()
    session = SessionLocal()
    try:
        with pytest.raises(api["SimulationBaselineMismatch"], match="risk-v1 high"):
            api["run_read_only_simulation"](
                session,
                run_id="run-1",
                baseline=_baseline(api, high_count=3),
            )

        assert list(tmp_path.iterdir()) == []
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()


def test_simulation_writes_deterministic_summary_transition_and_high_priority_files(tmp_path: Path):
    api = _simulation_api()
    engine, SessionLocal = _seed_simulation_database()
    session = SessionLocal()
    try:
        result = api["run_read_only_simulation"](
            session,
            run_id="run-1",
            baseline=_baseline(api),
        )

        paths = api["write_simulation_outputs"](result, tmp_path)

        assert set(paths) == {"summary", "transitions", "high_priority"}
        summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert summary["run_id"] == "run-1"
        assert summary["assessment_count"] == 4
        assert summary["old_priority_counts"]["high"] == 2
        assert summary["new_priority_counts"]["high"] == 1
        with (tmp_path / "transitions.csv").open(encoding="utf-8-sig", newline="") as handle:
            transitions = list(csv.DictReader(handle))
        with (tmp_path / "high_priority.csv").open(encoding="utf-8-sig", newline="") as handle:
            high_priority = list(csv.DictReader(handle))
        assert [row["requirement_id"] for row in transitions] == [
            "GRI 2-1-a",
            "GRI 2-1-b",
            "GRI 2-1-c",
            "GRI 2-1-d",
        ]
        assert [row["requirement_id"] for row in high_priority] == ["GRI 2-1-d"]
        assert "sufficiency_conflict" in high_priority[0]["new_reason_codes"]
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()
