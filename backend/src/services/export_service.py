import csv
import io

from src.db.repositories import Repository


def assessments_rows(repository: Repository, run_id: str) -> list[dict]:
    rows = []
    for assessment in repository.list_assessments_by_run(run_id):
        rows.append(
            {
                "assessment_id": assessment.assessment_id,
                "run_id": assessment.run_id,
                "report_id": assessment.report_id,
                "standard_id": assessment.standard_id,
                "standard_version": assessment.standard_version,
                "disclosure_id": assessment.disclosure_id,
                "requirement_id": assessment.requirement_id,
                "verdict": assessment.verdict.value,
                "rationale": assessment.rationale,
                "model_called": assessment.model_called,
                "review_status": assessment.review_status.value,
                "evidence_count": len(assessment.evidence),
            }
        )
    return rows


def review_rows(repository: Repository, run_id: str) -> list[dict]:
    rows = []
    for decision in repository.list_review_decisions_by_run(run_id):
        rows.append(
            {
                "decision_id": decision.decision_id,
                "run_id": decision.run_id,
                "assessment_id": decision.assessment_id,
                "review_status": decision.review_status.value,
                "reviewer_note": decision.reviewer_note,
                "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
            }
        )
    return rows


def rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()