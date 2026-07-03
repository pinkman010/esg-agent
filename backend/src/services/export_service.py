import csv
import io

from src.db.repositories import Repository


def assessments_rows(repository: Repository, run_id: str) -> list[dict]:
    rows = []
    for assessment in repository.list_assessments_by_run(run_id):
        first_evidence = assessment.evidence[0] if assessment.evidence else None
        source_pdf_page = first_evidence.source_pdf_page if first_evidence else None
        source_report_page = first_evidence.source_report_page if first_evidence else None
        candidate_pdf_pages = first_evidence.metadata.get("candidate_pdf_pages", []) if first_evidence else []
        candidate_report_pages = first_evidence.metadata.get("candidate_report_pages", []) if first_evidence else []
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
                "source_page": first_evidence.source_page if first_evidence else None,
                "source_pdf_page": source_pdf_page,
                "source_report_page": source_report_page,
                "page_label": format_page_label(source_pdf_page, source_report_page),
                "candidate_pdf_pages": candidate_pdf_pages,
                "candidate_report_pages": candidate_report_pages,
                "needs_ocr_or_vlm": first_evidence.needs_ocr_or_vlm if first_evidence else False,
                "requires_ocr": first_evidence.requires_ocr if first_evidence else False,
                "requires_vlm": first_evidence.requires_vlm if first_evidence else False,
                "ocr_or_vlm_reason": first_evidence.ocr_or_vlm_reason if first_evidence else None,
                "evidence_preview": first_evidence.evidence_preview if first_evidence else None,
            }
        )
    return rows


def format_page_label(source_pdf_page: int | None, source_report_page: int | None) -> str:
    if source_pdf_page and source_report_page:
        return f"PDF 第 {source_pdf_page} 页 / 报告页 {source_report_page}"
    if source_pdf_page:
        return f"PDF 第 {source_pdf_page} 页"
    return ""


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
