import argparse
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.db.models import AssessmentRiskRecord, ReportRecord
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.domain.enums import ReviewOperation, RiskLevel
from src.domain.models import DisclosureAssessment, ReviewSnapshot
from src.services.review_priority_service import (
    RISK_V2_RULE_VERSION,
    build_review_priority_context,
    classify_review_priority,
)


@dataclass(frozen=True)
class SimulationBaseline:
    eligible_assessment_count: int = 577
    risk_v1_high_count: int = 355
    unknown_high_count: int = 343


class SimulationBaselineMismatch(ValueError):
    pass


@dataclass(frozen=True)
class DatabaseFingerprint:
    assessment_risk_count: int
    latest_risk_calculated_at: datetime | None
    report_updated_at: datetime | None


@dataclass(frozen=True)
class SimulationRecord:
    assessment_id: str
    requirement_id: str
    system_verdict: str
    old_risk_level: str
    old_reason_codes: tuple[str, ...]
    new_review_priority: str
    new_evidence_status: str
    new_applicability_status: str
    new_reason_codes: tuple[str, ...]
    changed: bool
    evidence_types: tuple[str, ...]
    source_pdf_pages: tuple[int, ...]
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class SimulationResult:
    report_id: str
    run_id: str
    assessment_count: int
    risk_v2_rule_version: str
    old_priority_counts: dict[str, int]
    new_priority_counts: dict[str, int]
    old_reason_counts: dict[str, int]
    new_reason_counts: dict[str, int]
    evidence_status_counts: dict[str, int]
    applicability_counts: dict[str, int]
    transition_counts: dict[str, int]
    formal_output_gate: dict[str, int | bool]
    baseline: SimulationBaseline
    records: tuple[SimulationRecord, ...]

    def summary(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "assessment_count": self.assessment_count,
            "risk_v2_rule_version": self.risk_v2_rule_version,
            "read_only": True,
            "baseline": asdict(self.baseline),
            "old_priority_counts": self.old_priority_counts,
            "new_priority_counts": self.new_priority_counts,
            "old_reason_counts": self.old_reason_counts,
            "new_reason_counts": self.new_reason_counts,
            "evidence_status_counts": self.evidence_status_counts,
            "applicability_counts": self.applicability_counts,
            "transition_counts": self.transition_counts,
            "formal_output_gate": self.formal_output_gate,
            "changed_assessment_count": sum(record.changed for record in self.records),
            "high_priority_requirement_count": sum(
                record.new_review_priority == RiskLevel.HIGH.value
                for record in self.records
            ),
        }


def database_fingerprint(session: Session, report_id: str) -> DatabaseFingerprint:
    report_updated_at = session.scalar(
        select(ReportRecord.updated_at).where(ReportRecord.report_id == report_id)
    )
    if report_updated_at is None:
        raise LookupError(f"report not found: {report_id}")
    return DatabaseFingerprint(
        assessment_risk_count=int(
            session.scalar(select(func.count()).select_from(AssessmentRiskRecord)) or 0
        ),
        latest_risk_calculated_at=session.scalar(
            select(func.max(AssessmentRiskRecord.calculated_at))
        ),
        report_updated_at=report_updated_at,
    )


def run_read_only_simulation(
    session: Session,
    *,
    run_id: str,
    baseline: SimulationBaseline | None = None,
) -> SimulationResult:
    session.rollback()
    session.execute(text("SET TRANSACTION READ ONLY"))
    repo = Repository(session)
    run = repo.get_run(run_id)
    if run is None:
        session.rollback()
        raise LookupError(f"run not found: {run_id}")

    before = database_fingerprint(session, run.report_id)
    try:
        result = simulate_run(repo, run_id=run_id, baseline=baseline)
        after = database_fingerprint(session, run.report_id)
        if after != before:
            raise RuntimeError("risk-v2 simulation changed database state")
        return result
    finally:
        session.rollback()


def simulate_run(
    repo: Repository,
    *,
    run_id: str,
    baseline: SimulationBaseline | None = None,
) -> SimulationResult:
    expected = baseline or SimulationBaseline()
    run = repo.get_run(run_id)
    if run is None:
        raise LookupError(f"run not found: {run_id}")
    assessments = sorted(
        repo.list_assessments_by_run(run_id),
        key=lambda item: (item.requirement_id, item.assessment_id),
    )
    assessment_ids = [item.assessment_id for item in assessments]
    risks = repo.latest_risks_for_assessments(assessment_ids)
    snapshots = repo.latest_snapshots_for_assessments(assessment_ids)

    _validate_baseline(
        expected,
        run_eligible_count=run.eligible_requirement_count,
        assessments=assessments,
        risks=risks,
    )

    records: list[SimulationRecord] = []
    old_unresolved_high = 0
    new_unresolved_high = 0
    for assessment in assessments:
        old_risk = risks[assessment.assessment_id]
        snapshot = snapshots.get(assessment.assessment_id)
        effective_assessment = _effective_assessment(assessment, snapshot)
        evidence_invalidated = bool(
            snapshot and snapshot.operation_type is ReviewOperation.INVALIDATE_EVIDENCE
        )
        reopened = bool(snapshot and snapshot.operation_type is ReviewOperation.REOPEN)
        context = build_review_priority_context(
            effective_assessment,
            evidence_invalidated=evidence_invalidated,
            reopened=reopened,
        )
        classification = classify_review_priority(context)
        is_resolved = _is_resolved(snapshot)
        if old_risk.risk_level is RiskLevel.HIGH and not is_resolved:
            old_unresolved_high += 1
        if classification.review_priority is RiskLevel.HIGH and not is_resolved:
            new_unresolved_high += 1

        source_pdf_pages = tuple(
            sorted(
                {
                    item.source_pdf_page or item.source_page
                    for item in effective_assessment.evidence
                }
            )
        )
        quality_flags = tuple(
            sorted(
                {
                    flag.value
                    for item in effective_assessment.evidence
                    for flag in item.quality_flags
                }
            )
        )
        old_reasons = tuple(old_risk.reason_codes)
        new_reasons = tuple(classification.reason_codes)
        records.append(
            SimulationRecord(
                assessment_id=assessment.assessment_id,
                requirement_id=assessment.requirement_id,
                system_verdict=assessment.verdict.value,
                old_risk_level=old_risk.risk_level.value,
                old_reason_codes=old_reasons,
                new_review_priority=classification.review_priority.value,
                new_evidence_status=classification.evidence_status.value,
                new_applicability_status=classification.applicability_status.value,
                new_reason_codes=new_reasons,
                changed=(
                    old_risk.risk_level is not classification.review_priority
                    or old_reasons != new_reasons
                ),
                evidence_types=tuple(sorted(context.evidence_types)),
                source_pdf_pages=source_pdf_pages,
                quality_flags=quality_flags,
            )
        )

    old_priority_counts = _count(record.old_risk_level for record in records)
    new_priority_counts = _count(record.new_review_priority for record in records)
    return SimulationResult(
        report_id=run.report_id,
        run_id=run_id,
        assessment_count=len(records),
        risk_v2_rule_version=RISK_V2_RULE_VERSION,
        old_priority_counts=old_priority_counts,
        new_priority_counts=new_priority_counts,
        old_reason_counts=_count(
            reason
            for record in records
            for reason in record.old_reason_codes
        ),
        new_reason_counts=_count(
            reason
            for record in records
            for reason in record.new_reason_codes
        ),
        evidence_status_counts=_count(
            record.new_evidence_status for record in records
        ),
        applicability_counts=_count(
            record.new_applicability_status for record in records
        ),
        transition_counts=_count(
            f"{record.old_risk_level}->{record.new_review_priority}"
            for record in records
        ),
        formal_output_gate={
            "old_unresolved_high": old_unresolved_high,
            "new_unresolved_high": new_unresolved_high,
            "changed": old_unresolved_high != new_unresolved_high,
        },
        baseline=expected,
        records=tuple(records),
    )


def write_simulation_outputs(
    result: SimulationResult,
    output_dir: Path | str,
) -> dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    summary_path = directory / "summary.json"
    transitions_path = directory / "transitions.csv"
    high_priority_path = directory / "high_priority.csv"

    summary_path.write_text(
        json.dumps(result.summary(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_records(transitions_path, result.records)
    _write_records(
        high_priority_path,
        tuple(
            record
            for record in result.records
            if record.new_review_priority == RiskLevel.HIGH.value
        ),
    )
    return {
        "summary": summary_path,
        "transitions": transitions_path,
        "high_priority": high_priority_path,
    }


def _validate_baseline(
    expected: SimulationBaseline,
    *,
    run_eligible_count: int,
    assessments: Sequence[DisclosureAssessment],
    risks: dict[str, Any],
) -> None:
    high_count = sum(
        risk.risk_level is RiskLevel.HIGH
        for risk in risks.values()
    )
    unknown_high_count = sum(
        risk.risk_level is RiskLevel.HIGH and "unknown_verdict" in risk.reason_codes
        for risk in risks.values()
    )
    checks = [
        (
            "run eligible assessment",
            expected.eligible_assessment_count,
            run_eligible_count,
        ),
        (
            "persisted assessment",
            expected.eligible_assessment_count,
            len(assessments),
        ),
        (
            "latest risk",
            expected.eligible_assessment_count,
            len(risks),
        ),
        ("risk-v1 high", expected.risk_v1_high_count, high_count),
        ("unknown high", expected.unknown_high_count, unknown_high_count),
    ]
    mismatches = [
        f"{name}: expected {wanted}, actual {actual}"
        for name, wanted, actual in checks
        if wanted != actual
    ]
    if mismatches:
        raise SimulationBaselineMismatch("; ".join(mismatches))


def _effective_assessment(
    assessment: DisclosureAssessment,
    snapshot: ReviewSnapshot | None,
) -> DisclosureAssessment:
    if snapshot is None:
        return assessment
    evidence = (
        []
        if snapshot.operation_type is ReviewOperation.INVALIDATE_EVIDENCE
        else assessment.evidence
    )
    return assessment.model_copy(
        update={
            "verdict": snapshot.reviewed_verdict or assessment.verdict,
            "evidence": evidence,
            "rationale": snapshot.rationale or assessment.rationale,
            "missing_items": (
                snapshot.missing_items
                if snapshot.missing_items is not None
                else assessment.missing_items
            ),
        }
    )


def _is_resolved(snapshot: ReviewSnapshot | None) -> bool:
    return bool(
        snapshot
        and snapshot.operation_type
        in {
            ReviewOperation.APPROVE,
            ReviewOperation.MODIFY,
            ReviewOperation.LEGACY_IMPORT,
        }
    )


def _count(values) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _write_records(path: Path, records: Sequence[SimulationRecord]) -> None:
    fieldnames = [
        "assessment_id",
        "requirement_id",
        "system_verdict",
        "old_risk_level",
        "old_reason_codes",
        "new_review_priority",
        "new_evidence_status",
        "new_applicability_status",
        "new_reason_codes",
        "changed",
        "evidence_types",
        "source_pdf_pages",
        "quality_flags",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "assessment_id": record.assessment_id,
                    "requirement_id": record.requirement_id,
                    "system_verdict": record.system_verdict,
                    "old_risk_level": record.old_risk_level,
                    "old_reason_codes": json.dumps(
                        record.old_reason_codes,
                        ensure_ascii=False,
                    ),
                    "new_review_priority": record.new_review_priority,
                    "new_evidence_status": record.new_evidence_status,
                    "new_applicability_status": record.new_applicability_status,
                    "new_reason_codes": json.dumps(
                        record.new_reason_codes,
                        ensure_ascii=False,
                    ),
                    "changed": str(record.changed).lower(),
                    "evidence_types": json.dumps(
                        record.evidence_types,
                        ensure_ascii=False,
                    ),
                    "source_pdf_pages": json.dumps(record.source_pdf_pages),
                    "quality_flags": json.dumps(record.quality_flags),
                }
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only risk-v2 simulation for one analysis run."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-id")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-assessments", type=int, default=577)
    parser.add_argument("--expected-old-high", type=int, default=355)
    parser.add_argument("--expected-unknown-high", type=int, default=343)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    database_name = make_url(settings.database_url).database or ""
    session = SessionLocal()
    try:
        run = Repository(session).get_run(args.run_id)
        if run is None:
            raise LookupError(f"run not found: {args.run_id}")
        if args.report_id and run.report_id != args.report_id:
            raise ValueError(
                f"run report mismatch: expected {args.report_id}, actual {run.report_id}"
            )
        session.rollback()
        print(f"app_env={settings.app_env}")
        print(f"database={database_name}")
        print(f"report_id={run.report_id}")
        print(f"run_id={run.run_id}")
        print("read_only=true")
        result = run_read_only_simulation(
            session,
            run_id=args.run_id,
            baseline=SimulationBaseline(
                eligible_assessment_count=args.expected_assessments,
                risk_v1_high_count=args.expected_old_high,
                unknown_high_count=args.expected_unknown_high,
            ),
        )
        paths = write_simulation_outputs(result, args.output_dir)
        print(json.dumps(result.summary(), ensure_ascii=False, sort_keys=True))
        for name, path in paths.items():
            print(f"{name}={path}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
