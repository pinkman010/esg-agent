import csv
import io
from hashlib import sha256
from pathlib import Path

from openpyxl import Workbook
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from src.db.repositories import Repository
from src.domain.enums import ReportStatus, RiskLevel
from src.domain.models import ExportVersion


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


class VersionedExportService:
    def __init__(self, repository: Repository, output_root: Path):
        self.repository = repository
        self.output_root = Path(output_root)

    def generate(
        self,
        report_id: str,
        *,
        is_draft: bool,
        formats: list[str],
        created_by: str,
    ) -> ExportVersion:
        run = self.repository.latest_run_for_report(report_id)
        if run is None:
            raise ValueError("report has no analysis run")
        assessments = self.repository.list_assessments_by_run(run.run_id)
        ids = [item.assessment_id for item in assessments]
        risks = self.repository.latest_risks_for_assessments(ids)
        snapshots = self.repository.latest_snapshots_for_assessments(ids)
        high_ids = [item.assessment_id for item in assessments if not risks.get(item.assessment_id) or risks[item.assessment_id].risk_level is RiskLevel.HIGH]
        reviewed_high = [item for item in high_ids if item in snapshots and snapshots[item].operation_type.value in {"approve", "modify", "legacy_import"}]
        if not is_draft and len(reviewed_high) != len(high_ids):
            raise PermissionError(f"high risk review incomplete: {len(high_ids) - len(reviewed_high)}")

        export_id = self.repository.new_export_id()
        version_number = 0 if is_draft else self.repository.next_formal_export_version(report_id)
        previous = None if is_draft else self.repository.latest_formal_export(report_id)
        destination = self.output_root / "exports" / report_id / export_id
        destination.mkdir(parents=True, exist_ok=True)
        rows = assessments_rows(self.repository, run.run_id)
        manifest = [self._write_format(destination, item, rows, report_id, is_draft) for item in formats]
        digest = sha256("".join(item["sha256"] for item in manifest).encode()).hexdigest()
        export = self.repository.save_export_version(
            ExportVersion(
                export_id=export_id,
                report_id=report_id,
                run_id=run.run_id,
                version_number=version_number,
                status="draft" if is_draft else "formal",
                is_draft=is_draft,
                file_hash=digest,
                engine_version=run.engine_version,
                risk_rule_version=run.risk_rule_version,
                review_scope={
                    "high_risk_total": len(high_ids),
                    "high_risk_reviewed": len(reviewed_high),
                    "system_pending_count": len(assessments) - len(snapshots),
                    "draft_label": is_draft,
                },
                file_manifest=manifest,
                supersedes_export_id=previous.export_id if previous else None,
                created_by=created_by,
            )
        )
        if previous:
            self.repository.mark_export_superseded(previous.export_id)
        if not is_draft:
            self.repository.update_report_status(report_id, ReportStatus.FORMALLY_EXPORTED)
        return export

    def _write_format(self, destination: Path, format_name: str, rows: list[dict], report_id: str, is_draft: bool) -> dict:
        if format_name in {"assessment_xlsx", "actions_xlsx"}:
            path = destination / f"{format_name}.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "GRI核查" if format_name == "assessment_xlsx" else "整改任务"
            if rows:
                sheet.append(list(rows[0].keys()))
                for row in rows:
                    sheet.append([str(row.get(key, "")) for key in rows[0].keys()])
            workbook.save(path)
        elif format_name == "management_pdf":
            path = destination / "management-summary.pdf"
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            doc = canvas.Canvas(str(path))
            doc.setFont("STSong-Light", 14)
            doc.drawString(50, 800, "ESG 管理层摘要" + ("（草稿）" if is_draft else ""))
            doc.setFont("STSong-Light", 10)
            doc.drawString(50, 775, f"报告：{report_id}  核查条目：{len(rows)}")
            doc.save()
        elif format_name == "print_html":
            path = destination / "print.html"
            label = "<strong>草稿</strong>" if is_draft else "正式版本"
            path.write_text(f"<!doctype html><html lang='zh'><meta charset='utf-8'><title>ESG 核查</title><body><h1>ESG 核查表</h1><p>{label}</p><p>共 {len(rows)} 条</p></body></html>", encoding="utf-8")
        else:
            raise ValueError(f"unsupported export format: {format_name}")
        content = path.read_bytes()
        return {"format": format_name, "path": path.as_posix(), "size": len(content), "sha256": sha256(content).hexdigest()}
