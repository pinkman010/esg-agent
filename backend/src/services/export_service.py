import csv
import html
import io
import json
import shutil
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from openpyxl import Workbook
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from src.db.repositories import Repository, new_id
from src.domain.enums import ReportStatus, RiskLevel
from src.domain.models import ExportVersion, ImprovementAction
from src.services.analysis_runner import GRI_REQUIREMENTS_PATH
from src.services.effective_run_view_service import EffectiveRunViewService
from src.services.presentation_localization import localize_missing_items, localize_rationale
from src.services.requirement_scope_service import RequirementScopeService
from src.standards.gri import GRIAdapter
from src.domain.versions import CURRENT_RISK_RULE_VERSION


AI_DISCLAIMER = "AI建议未经人工确认时不构成最终披露结论。"
ACTIONS_DISCLAIMER = (
    "本清单为整改任务跟踪材料；任务状态和截止日期"
    "不构成 GRI 认证或外部鉴证结论。"
)
ACTION_EXPORT_HEADERS = [
    "整改任务 ID",
    "Requirement ID",
    "任务标题",
    "优先级",
    "状态",
    "负责人",
    "截止日期",
    "建议内容",
    "完成说明",
    "创建人",
    "创建时间",
    "更新时间",
]


class ExportFileNotFoundError(FileNotFoundError):
    pass


class ExportFileIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedExportFile:
    path: Path
    filename: str
    format: str
    size: int
    sha256: str


class ExportGateError(PermissionError):
    def __init__(self, code: str, remaining: int):
        super().__init__(f"{code}: {remaining}")
        self.code = code
        self.remaining = remaining


def _manifest_file_id(
    export: ExportVersion,
    index: int,
    item: dict,
) -> str:
    existing = item.get("file_id")
    if existing:
        return str(existing)
    identity = ":".join(
        [
            export.export_id,
            str(index),
            str(item.get("format") or ""),
            str(item.get("sha256") or ""),
        ]
    )
    return f"file-legacy-{sha256(identity.encode()).hexdigest()[:32]}"


def _manifest_filename(item: dict) -> str:
    source = (
        item.get("filename")
        or item.get("relative_path")
        or item.get("path")
        or item.get("format")
        or "export-file"
    )
    return Path(str(source)).name


def public_export_manifest(export: ExportVersion) -> list[dict[str, object]]:
    return [
        {
            "file_id": _manifest_file_id(export, index, item),
            "filename": _manifest_filename(item),
            "format": str(item.get("format") or ""),
            "size": int(item.get("size") or 0),
            "sha256": str(item.get("sha256") or ""),
        }
        for index, item in enumerate(export.file_manifest)
    ]


def resolve_export_file(
    export: ExportVersion,
    file_id: str,
    *,
    output_root: Path,
) -> ResolvedExportFile:
    manifest_item = None
    for index, item in enumerate(export.file_manifest):
        if _manifest_file_id(export, index, item) == file_id:
            manifest_item = item
            break
    if manifest_item is None:
        raise ExportFileNotFoundError

    stored_path = (
        manifest_item.get("relative_path")
        if "relative_path" in manifest_item
        else manifest_item.get("path")
    )
    if not stored_path:
        raise ExportFileNotFoundError

    output_root = Path(output_root)
    candidate = Path(str(stored_path))
    if not candidate.is_absolute():
        candidate = output_root / candidate
    try:
        allowed_root = (
            output_root / "exports" / export.report_id / export.export_id
        ).resolve(strict=True)
        resolved_path = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise ExportFileNotFoundError from None
    if not resolved_path.is_file() or not resolved_path.is_relative_to(
        allowed_root
    ):
        raise ExportFileNotFoundError

    content = resolved_path.read_bytes()
    actual_size = len(content)
    actual_sha256 = sha256(content).hexdigest()
    if (
        actual_size != int(manifest_item.get("size") or -1)
        or actual_sha256 != str(manifest_item.get("sha256") or "")
    ):
        raise ExportFileIntegrityError
    return ResolvedExportFile(
        path=resolved_path,
        filename=_manifest_filename(manifest_item),
        format=str(manifest_item.get("format") or ""),
        size=actual_size,
        sha256=actual_sha256,
    )


def assessments_rows(repository: Repository, run_id: str) -> list[dict]:
    return assessment_rows_from_assessments(
        repository,
        repository.list_assessments_by_run(run_id),
    )


def assessment_rows_from_assessments(
    repository: Repository,
    assessments: list,
) -> list[dict]:
    rows = []
    for assessment in assessments:
        task = repository.get_disclosure_task(
            assessment.run_id,
            assessment.requirement_id,
        )
        ai_suggestion = repository.get_latest_ai_suggestion(assessment.assessment_id)
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
                "structure_status": task.structure_status if task else "legacy_unavailable",
                "source_requirement_text": (
                    task.source_requirement_text if task and task.source_requirement_text else assessment.requirement_id
                ),
                "effective_requirement_text": (
                    task.requirement_text if task else assessment.requirement_id
                ),
                "verdict": assessment.verdict.value,
                "rationale": assessment.rationale,
                "rationale_zh": localize_rationale(assessment.rationale),
                "missing_items": assessment.missing_items,
                "missing_items_zh": localize_missing_items(assessment.missing_items),
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
                "ai_status": ai_suggestion.status.value if ai_suggestion else None,
                "ai_suggested_verdict": (
                    ai_suggestion.suggested_verdict.value
                    if ai_suggestion and ai_suggestion.suggested_verdict
                    else None
                ),
                "ai_rationale_zh": ai_suggestion.rationale_zh if ai_suggestion else None,
                "ai_missing_items_zh": ai_suggestion.missing_items_zh if ai_suggestion else [],
                "ai_evidence_pdf_pages": ai_suggestion.evidence_pdf_pages if ai_suggestion else [],
                "ai_model": ai_suggestion.model if ai_suggestion else None,
                "ai_prompt_version": ai_suggestion.prompt_version if ai_suggestion else None,
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


def action_export_rows(
    actions: list[ImprovementAction],
    requirement_ids_by_assessment: dict[str, str],
) -> list[dict[str, object]]:
    return [
        {
            "整改任务 ID": action.action_id,
            "Requirement ID": requirement_ids_by_assessment.get(
                action.assessment_id,
                "",
            ),
            "任务标题": action.title,
            "优先级": action.priority.value,
            "状态": action.status.value,
            "负责人": action.owner_name,
            "截止日期": action.due_date.isoformat()
            if action.due_date
            else None,
            "建议内容": action.recommendation_text,
            "完成说明": action.completion_note,
            "创建人": action.created_by,
            "创建时间": action.created_at.isoformat()
            if action.created_at
            else None,
            "更新时间": action.updated_at.isoformat()
            if action.updated_at
            else None,
        }
        for action in actions
    ]


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
        supported_formats = {
            "assessment_xlsx",
            "actions_xlsx",
            "management_pdf",
            "print_html",
        }
        unsupported_formats = [item for item in formats if item not in supported_formats]
        if unsupported_formats:
            raise ValueError(
                f"unsupported export format: {unsupported_formats[0]}"
            )
        run = self.repository.latest_run_for_report(report_id)
        if run is None:
            raise ValueError("report has no analysis run")
        adapter = GRIAdapter(GRI_REQUIREMENTS_PATH)
        scope_summary = adapter.get_scope_summary()
        effective_view_service = EffectiveRunViewService(self.repository)
        uses_complete_scope = (
            effective_view_service.lineage_contains_eligible_count(
                latest_run=run,
                eligible_count=scope_summary["independent_assessment_count"],
            )
        )
        effective_incomplete_total = 0
        if uses_complete_scope:
            independent_ids = {
                requirement.requirement_id
                for requirement in adapter.load_requirements()
            }
            effective_view = effective_view_service.build(
                report_id=report_id,
                independent_requirement_ids=independent_ids,
            )
            assessments = [
                effective.assessment
                for effective in (
                    effective_view.assessments_by_requirement.values()
                )
            ]
            effective_incomplete_total = (
                len(effective_view.failed_requirement_ids)
                + len(effective_view.not_generated_requirement_ids)
            )
        else:
            assessments = self.repository.list_assessments_by_run(run.run_id)
        ids = [item.assessment_id for item in assessments]
        risks = self.repository.latest_risks_for_assessments(ids)
        snapshots = self.repository.latest_snapshots_for_assessments(ids)
        resolved_operations = {"approve", "modify", "legacy_import"}
        high_ids = [
            item.assessment_id
            for item in assessments
            if not risks.get(item.assessment_id)
            or risks[item.assessment_id].risk_level is RiskLevel.HIGH
        ]
        medium_ids = [
            item.assessment_id
            for item in assessments
            if risks.get(item.assessment_id)
            and risks[item.assessment_id].risk_level is RiskLevel.MEDIUM
        ]
        reviewed_ids = {
            assessment_id
            for assessment_id, snapshot in snapshots.items()
            if snapshot.operation_type.value in resolved_operations
        }
        reviewed_high = [item for item in high_ids if item in reviewed_ids]
        reviewed_medium = [item for item in medium_ids if item in reviewed_ids]
        applicability_undetermined = [
            item.assessment_id
            for item in assessments
            if risks.get(item.assessment_id)
            and risks[item.assessment_id].applicability_status is not None
            and risks[item.assessment_id].applicability_status.value == "undetermined"
        ]
        uses_current_risk_rule = run.risk_rule_version == CURRENT_RISK_RULE_VERSION
        eligible_total = (
            scope_summary["independent_assessment_count"]
            if uses_complete_scope
            else run.eligible_requirement_count
            if uses_current_risk_rule
            else len(assessments)
        )
        analysis_incomplete_total = (
            effective_incomplete_total
            if uses_complete_scope
            else
            max(
                run.failed_requirement_count,
                eligible_total - run.succeeded_requirement_count,
                eligible_total - len(assessments),
                0,
            )
            if uses_current_risk_rule
            else run.failed_requirement_count
        )
        standard_unit_total = (
            scope_summary["standard_unit_count"]
            if uses_complete_scope
            else eligible_total
        )
        high_priority_total = (
            len(high_ids) + analysis_incomplete_total
            if uses_complete_scope
            else len(high_ids)
        )
        high_priority_unresolved = (
            high_priority_total - len(reviewed_high)
        )
        review_scope_statement = (
            f"当前仍有高复核优先级未处理 {high_priority_unresolved} 条、"
            f"分析失败或未生成结果 {analysis_incomplete_total} 条；"
            + (
                f"不代表核查范围 {standard_unit_total} 项均已人工确认。"
                if uses_complete_scope
                else f"不代表全部 {standard_unit_total} 条均已人工确认。"
            )
            if high_priority_unresolved or analysis_incomplete_total
            else (
                "高复核优先级项目已处理；"
                + (
                    f"不代表核查范围 {standard_unit_total} 项均已人工确认。"
                    if uses_complete_scope
                    else f"不代表全部 {standard_unit_total} 条均已人工确认。"
                )
            )
        )
        if not is_draft and analysis_incomplete_total:
            raise ExportGateError("analysis_incomplete", analysis_incomplete_total)
        if not is_draft and len(reviewed_high) != len(high_ids):
            raise ExportGateError(
                "high_risk_review_incomplete",
                high_priority_unresolved,
            )

        export_id = self.repository.new_export_id()
        version_number = 0 if is_draft else self.repository.next_formal_export_version(report_id)
        previous = None if is_draft else self.repository.latest_formal_export(report_id)
        destination = self.output_root / "exports" / report_id / export_id
        assessment_rows = assessment_rows_from_assessments(
            self.repository,
            assessments,
        )
        rows = (
            self._complete_scope_rows(
                report_id=report_id,
                adapter=adapter,
                assessment_rows=assessment_rows,
            )
            if uses_complete_scope
            else assessment_rows
        )
        actions = (
            self.repository.list_improvement_actions(report_id)
            if "actions_xlsx" in formats
            else []
        )
        requirement_ids_by_assessment = {}
        for action in actions:
            assessment = self.repository.get_assessment(action.assessment_id)
            if assessment is not None:
                requirement_ids_by_assessment[action.assessment_id] = (
                    assessment.requirement_id
                )
        action_rows = action_export_rows(
            actions,
            requirement_ids_by_assessment,
        )
        destination.mkdir(parents=True, exist_ok=True)
        try:
            manifest = [
                self._write_format(
                    destination,
                    item,
                    rows,
                    report_id,
                    is_draft,
                    action_rows=action_rows,
                )
                for item in formats
            ]
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
        digest = sha256("".join(item["sha256"] for item in manifest).encode()).hexdigest()
        export_version = ExportVersion(
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
                "high_risk_total": high_priority_total,
                "high_risk_reviewed": len(reviewed_high),
                "high_priority_total": high_priority_total,
                "high_priority_reviewed": len(reviewed_high),
                "high_priority_unresolved": high_priority_unresolved,
                "medium_priority_total": len(medium_ids),
                "medium_priority_reviewed": len(reviewed_medium),
                "medium_priority_unresolved": len(medium_ids) - len(reviewed_medium),
                "applicability_undetermined_total": len(applicability_undetermined),
                "analysis_incomplete_total": analysis_incomplete_total,
                "eligible_requirement_total": eligible_total,
                "standard_unit_total": standard_unit_total,
                "human_reviewed_total": len(reviewed_ids.intersection(ids)),
                "review_scope_statement": review_scope_statement,
                "system_pending_count": (
                    eligible_total - len(snapshots)
                    if uses_complete_scope
                    else len(assessments) - len(snapshots)
                ),
                "draft_label": is_draft,
            },
            file_manifest=manifest,
            supersedes_export_id=previous.export_id if previous else None,
            created_by=created_by,
        )
        try:
            export = self.repository.save_export_version(
                export_version,
                commit=False,
            )
            if previous:
                self.repository.mark_export_superseded(
                    previous.export_id,
                    commit=False,
                )
            if not is_draft:
                self.repository.update_report_status(
                    report_id,
                    ReportStatus.FORMALLY_EXPORTED,
                    commit=False,
                )
            self.repository.create_audit_event(
                run.run_id,
                "draft_export_created" if is_draft else "formal_export_created",
                {
                    "report_id": report_id,
                    "export_id": export.export_id,
                    "version_number": export.version_number,
                    "formats": list(formats),
                    "supersedes_export_id": export.supersedes_export_id,
                },
                commit=False,
            )
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            shutil.rmtree(destination, ignore_errors=True)
            raise
        return export

    def _complete_scope_rows(
        self,
        *,
        report_id: str,
        adapter: GRIAdapter,
        assessment_rows: list[dict],
    ) -> list[dict]:
        scope_rows = RequirementScopeService(
            self.repository,
            adapter,
        ).list_items(report_id)
        details_by_assessment = {
            row["assessment_id"]: row for row in assessment_rows
        }
        rows = []
        for scope_row in scope_rows:
            detail = details_by_assessment.get(scope_row["assessment_id"], {})
            row = {**detail, **scope_row}
            if scope_row["unit_status"] == "context_incorporated":
                row["scope_note"] = "已作为上下文纳入相关判断"
            else:
                row["scope_note"] = ""
            rows.append(row)
        return rows

    def _write_format(
        self,
        destination: Path,
        format_name: str,
        rows: list[dict],
        report_id: str,
        is_draft: bool,
        *,
        action_rows: list[dict[str, object]],
    ) -> dict:
        if format_name == "assessment_xlsx":
            path = destination / f"{format_name}.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "GRI核查"
            sheet.append([AI_DISCLAIMER])
            if rows:
                sheet.append(list(rows[0].keys()))
                for row in rows:
                    sheet.append(
                        [
                            _xlsx_value(row.get(key))
                            for key in rows[0].keys()
                        ]
                    )
            workbook.save(path)
        elif format_name == "actions_xlsx":
            path = destination / f"{format_name}.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "整改任务"
            sheet.append([ACTIONS_DISCLAIMER])
            sheet.append(ACTION_EXPORT_HEADERS)
            for row in action_rows:
                sheet.append(
                    [
                        _xlsx_value(row.get(header))
                        for header in ACTION_EXPORT_HEADERS
                    ]
                )
            workbook.save(path)
        elif format_name == "management_pdf":
            path = destination / "management-summary.pdf"
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            doc = canvas.Canvas(str(path))
            doc.setFont("STSong-Light", 14)
            doc.drawString(50, 800, "ESG 管理层摘要" + ("（草稿）" if is_draft else ""))
            doc.setFont("STSong-Light", 10)
            doc.drawString(50, 775, f"报告：{report_id}  核查条目：{len(rows)}")
            doc.drawString(50, 755, AI_DISCLAIMER)
            doc.save()
        elif format_name == "print_html":
            path = destination / "print.html"
            label = "<strong>草稿</strong>" if is_draft else "正式版本"
            table_rows = []
            for row in rows:
                unit_status = str(row.get("unit_status") or "assessed")
                conclusion = (
                    "已作为上下文纳入相关判断"
                    if unit_status == "context_incorporated"
                    else "分析失败（待重试）"
                    if row.get("analysis_status") == "failed"
                    else "尚未生成分析结果"
                    if row.get("analysis_status") == "not_generated"
                    else str(
                        row.get("effective_verdict")
                        or row.get("verdict")
                        or ""
                    )
                )
                table_rows.append(
                    '<tr data-unit-status="'
                    + html.escape(unit_status)
                    + '"><td>'
                    + html.escape(str(row.get("requirement_id") or ""))
                    + "</td><td>"
                    + html.escape(conclusion)
                    + "</td><td>"
                    + html.escape(str(row.get("review_priority") or ""))
                    + "</td><td>"
                    + html.escape(str(row.get("review_status") or ""))
                    + "</td><td>"
                    + html.escape(str(row.get("source_pdf_pages") or ""))
                    + "</td></tr>"
                )
            path.write_text(
                "<!doctype html><html lang='zh'><meta charset='utf-8'>"
                "<title>ESG 核查</title><body><h1>ESG 核查表</h1>"
                f"<p>{label}</p><p>{AI_DISCLAIMER}</p>"
                f"<p>共 {len(rows)} 项</p>"
                "<table><thead><tr><th>Requirement</th><th>结论</th>"
                "<th>复核优先级</th><th>复核状态</th><th>证据页</th>"
                "</tr></thead><tbody>"
                + "".join(table_rows)
                + "</tbody></table></body></html>",
                encoding="utf-8",
            )
        else:
            raise ValueError(f"unsupported export format: {format_name}")
        content = path.read_bytes()
        return {
            "file_id": new_id("file"),
            "format": format_name,
            "filename": path.name,
            "relative_path": path.relative_to(self.output_root).as_posix(),
            "size": len(content),
            "sha256": sha256(content).hexdigest(),
        }


def _xlsx_value(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value
