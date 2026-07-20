from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.db.models import (
    AIAssessmentSuggestionRecord,
    AnalysisRunRecord,
    AnalysisStageEventRecord,
    DisclosureTaskRecord,
    DocumentChunkRecord,
    DocumentPageRecord,
    AssessmentRecord,
    AssessmentRiskRecord,
    AuditEventRecord,
    EvidenceItemRecord,
    ExportVersionRecord,
    ImprovementActionRecord,
    RecommendationRecord,
    ReportRecord,
    ReviewDecisionRecord,
    ReviewSnapshotRecord,
    ReviewChangeEventRecord,
)
from src.domain.ai_models import AIAssessmentSuggestion
from src.domain.enums import AISuggestionStatus, ActionPriority, ActionStatus, ApplicabilityStatus, AssessmentVerdict, EvidenceSourceMethod, EvidenceStatus, PageQualityFlag, ReportStatus, ReviewOperation, ReviewStatus, RiskLevel, RunStatus
from src.domain.models import AnalysisRun, AnalysisStageEvent, AssessmentRisk, DisclosureAssessment, DisclosureTask, DocumentChunk, EvidenceItem, ExportVersion, ImprovementAction, PageExtraction, Recommendation, Report, ReviewChangeEvent, ReviewDecision, ReviewSnapshot


ACTIVE_RUN_CONSTRAINT_NAME = "uq_analysis_runs_one_active_per_report"
ACTIVE_RUN_STATUSES = {RunStatus.PENDING, RunStatus.RUNNING}
TERMINAL_RUN_STATUSES = {RunStatus.COMPLETED, RunStatus.PARTIALLY_COMPLETED, RunStatus.FAILED}
METADATA_CONFIRMABLE_REPORT_STATUSES = {
    ReportStatus.UPLOADED,
    ReportStatus.METADATA_DETECTED,
    ReportStatus.AWAITING_CONFIRMATION,
    ReportStatus.READY_FOR_ANALYSIS,
}


class ReportMetadataLockedError(ValueError):
    pass


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def rollback(self) -> None:
        self.session.rollback()

    def get_current_database(self) -> str:
        database_name = self.session.scalar(text("SELECT current_database()"))
        return str(database_name or "")

    def clear_demo_business_data(self) -> int:
        report_count = self.session.scalar(select(func.count()).select_from(ReportRecord)) or 0
        self.session.execute(delete(AuditEventRecord))
        self.session.execute(delete(ReportRecord))
        self.session.commit()
        return int(report_count)

    def create_report(self, report: Report) -> Report:
        record = ReportRecord(
            report_id=report.report_id,
            original_filename=report.original_filename,
            stored_path=report.stored_path,
            file_hash=report.file_hash,
            page_count=report.page_count,
            company_name=report.company_name,
            report_year=report.report_year,
            language=report.language,
            status=report.status.value,
            metadata_detected=report.metadata_detected,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._report_from_record(record)

    def get_report(self, report_id: str) -> Report | None:
        record = self.session.get(ReportRecord, report_id)
        if record is None:
            return None
        return self._report_from_record(record)

    def find_report_by_hash(self, file_hash: str) -> Report | None:
        record = self.session.scalar(
            select(ReportRecord)
            .where(ReportRecord.file_hash == file_hash)
            .order_by(ReportRecord.created_at.desc(), ReportRecord.report_id.desc())
        )
        return self._report_from_record(record) if record is not None else None

    def list_reports(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        status: ReportStatus | None = None,
    ) -> tuple[list[Report], int]:
        filters = [] if status is None else [ReportRecord.status == status.value]
        total = self.session.scalar(select(func.count()).select_from(ReportRecord).where(*filters)) or 0
        records = self.session.scalars(
            select(ReportRecord)
            .where(*filters)
            .order_by(ReportRecord.created_at.desc(), ReportRecord.report_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return [self._report_from_record(record) for record in records], total

    def confirm_report_metadata(
        self,
        report_id: str,
        *,
        company_name: str,
        report_year: int,
        language: str,
    ) -> Report:
        record = self.session.get(ReportRecord, report_id)
        if record is None:
            raise ValueError(f"report not found: {report_id}")
        if ReportStatus(record.status) not in METADATA_CONFIRMABLE_REPORT_STATUSES:
            raise ReportMetadataLockedError("报告已进入分析流程")
        record.company_name = company_name
        record.report_year = report_year
        record.language = language
        record.status = ReportStatus.READY_FOR_ANALYSIS.value
        record.metadata_confirmed_at = func.now()
        record.updated_at = func.now()
        self.session.commit()
        self.session.refresh(record)
        return self._report_from_record(record)

    def update_report_status(
        self,
        report_id: str,
        status: ReportStatus,
        *,
        commit: bool = True,
    ) -> Report:
        record = self.session.get(ReportRecord, report_id)
        if record is None:
            raise ValueError(f"report not found: {report_id}")
        record.status = status.value
        record.updated_at = func.now()
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        self.session.refresh(record)
        return self._report_from_record(record)

    def get_active_run_for_report(self, report_id: str) -> AnalysisRun | None:
        record = self.session.scalar(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.report_id == report_id,
                AnalysisRunRecord.status.in_([status.value for status in ACTIVE_RUN_STATUSES]),
            )
        )
        if record is None:
            return None
        return self._run_from_record(record)

    def create_run(self, run: AnalysisRun) -> AnalysisRun:
        if run.status in ACTIVE_RUN_STATUSES:
            active_run = self.get_active_run_for_report(run.report_id)
            if active_run is not None:
                raise ValueError(f"active analysis run already exists: {active_run.run_id}")

        record = AnalysisRunRecord(
            run_id=run.run_id,
            report_id=run.report_id,
            status=run.status.value,
            confirm_llm=run.confirm_llm,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            parent_run_id=run.parent_run_id,
            engine_version=run.engine_version,
            risk_rule_version=run.risk_rule_version,
            standard_unit_count=run.standard_unit_count,
            eligible_requirement_count=run.eligible_requirement_count,
            context_only_count=run.context_only_count,
            method_pending_count=run.method_pending_count,
            succeeded_requirement_count=run.succeeded_requirement_count,
            failed_requirement_count=run.failed_requirement_count,
            failure_summary=run.failure_summary,
        )
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            diagnostic = getattr(exc.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) == ACTIVE_RUN_CONSTRAINT_NAME:
                raise ValueError("active analysis run already exists") from exc
            raise
        self.session.refresh(record)
        return self._run_from_record(record)

    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        error_message: str | None = None,
        *,
        eligible_requirement_count: int | None = None,
        succeeded_requirement_count: int | None = None,
        failed_requirement_count: int | None = None,
        failure_summary: dict | None = None,
    ) -> AnalysisRun:
        record = self.session.get(AnalysisRunRecord, run_id)
        if record is None:
            raise ValueError(f"run not found: {run_id}")
        if status == RunStatus.RUNNING and record.started_at is None:
            record.started_at = func.now()
        if status in TERMINAL_RUN_STATUSES and record.completed_at is None:
            record.completed_at = func.now()
        record.status = status.value
        record.error_message = error_message
        if eligible_requirement_count is not None:
            record.eligible_requirement_count = eligible_requirement_count
        if succeeded_requirement_count is not None:
            record.succeeded_requirement_count = succeeded_requirement_count
        if failed_requirement_count is not None:
            record.failed_requirement_count = failed_requirement_count
        if failure_summary is not None:
            record.failure_summary = failure_summary
        self.session.commit()
        self.session.refresh(record)
        return self._run_from_record(record)

    def append_analysis_stage_event(self, event: AnalysisStageEvent) -> AnalysisStageEvent:
        record = AnalysisStageEventRecord(
            run_id=event.run_id,
            stage_code=event.stage_code,
            status=event.status,
            completed_units=event.completed_units,
            total_units=event.total_units,
            error_summary=event.error_summary,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._stage_event_from_record(record)

    def list_latest_analysis_stages(self, run_id: str) -> list[AnalysisStageEvent]:
        records = self.session.scalars(
            select(AnalysisStageEventRecord)
            .where(AnalysisStageEventRecord.run_id == run_id)
            .order_by(AnalysisStageEventRecord.created_at.desc(), AnalysisStageEventRecord.stage_event_id.desc())
        ).all()
        latest: dict[str, AnalysisStageEventRecord] = {}
        for record in records:
            latest.setdefault(record.stage_code, record)
        stage_order = [
            "file_validation",
            "pdf_parsing",
            "report_structure",
            "requirement_matching",
            "evidence_assessment",
            "risk_classification",
            "result_summary",
        ]
        order = {code: index for index, code in enumerate(stage_order)}
        return [self._stage_event_from_record(record) for record in sorted(latest.values(), key=lambda item: order.get(item.stage_code, 999))]

    def create_retry_run(self, parent_run_id: str, *, reason: str) -> AnalysisRun:
        parent = self.session.get(AnalysisRunRecord, parent_run_id)
        if parent is None:
            raise ValueError(f"run not found: {parent_run_id}")
        failed_ids = list(parent.failure_summary.get("failed_requirement_ids", []))
        if not failed_ids:
            raise ValueError("run has no failed requirements")
        return self.create_run(
            AnalysisRun(
                run_id=new_id("run"),
                report_id=parent.report_id,
                status=RunStatus.PENDING,
                confirm_llm=parent.confirm_llm,
                parent_run_id=parent_run_id,
                engine_version=parent.engine_version,
                risk_rule_version=parent.risk_rule_version,
                eligible_requirement_count=len(failed_ids),
                failure_summary={"retry_requirement_ids": failed_ids, "reason": reason},
            )
        )

    def list_runs(self) -> list[AnalysisRun]:
        records = self.session.scalars(select(AnalysisRunRecord).order_by(AnalysisRunRecord.run_id)).all()
        return [self._run_from_record(record) for record in records]
    def get_run(self, run_id: str) -> AnalysisRun | None:
        record = self.session.get(AnalysisRunRecord, run_id)
        if record is None:
            return None
        return self._run_from_record(record)

    def list_active_runs(self) -> list[AnalysisRun]:
        records = self.session.scalars(
            select(AnalysisRunRecord)
            .where(AnalysisRunRecord.status.in_([status.value for status in ACTIVE_RUN_STATUSES]))
            .order_by(AnalysisRunRecord.run_id)
        ).all()
        return [self._run_from_record(record) for record in records]

    def list_recommendations_by_run(self, run_id: str) -> list[Recommendation]:
        records = self.session.scalars(
            select(RecommendationRecord)
            .where(RecommendationRecord.run_id == run_id)
            .order_by(RecommendationRecord.recommendation_id)
        ).all()
        return [self._recommendation_from_record(record) for record in records]

    def list_review_runs(self) -> list[AnalysisRun]:
        records = self.session.scalars(
            select(AnalysisRunRecord)
            .join(AssessmentRecord, AssessmentRecord.run_id == AnalysisRunRecord.run_id)
            .where(AssessmentRecord.review_status == ReviewStatus.NEEDS_MANUAL_REVIEW.value)
            .order_by(AnalysisRunRecord.run_id)
            .distinct()
        ).all()
        return [self._run_from_record(record) for record in records]

    def list_review_decisions_by_run(self, run_id: str) -> list[ReviewDecision]:
        records = self.session.scalars(
            select(ReviewDecisionRecord)
            .where(ReviewDecisionRecord.run_id == run_id)
            .order_by(ReviewDecisionRecord.decision_id)
        ).all()
        return [self._review_decision_from_record(record) for record in records]

    def save_assessment(self, assessment: DisclosureAssessment) -> DisclosureAssessment:
        record = AssessmentRecord(
            assessment_id=assessment.assessment_id,
            run_id=assessment.run_id,
            report_id=assessment.report_id,
            standard_id=assessment.standard_id,
            standard_version=assessment.standard_version,
            disclosure_id=assessment.disclosure_id,
            requirement_id=assessment.requirement_id,
            verdict=assessment.verdict.value,
            rationale=assessment.rationale,
            missing_items=assessment.missing_items,
            model_called=assessment.model_called,
            review_status=assessment.review_status.value,
        )
        self.session.add(record)
        self.session.commit()
        return assessment

    def save_evidence_item(self, assessment_id: str, evidence: EvidenceItem) -> EvidenceItem:
        record = EvidenceItemRecord(
            evidence_id=evidence.evidence_id,
            assessment_id=assessment_id,
            run_id=evidence.run_id,
            report_id=evidence.report_id,
            source_text=evidence.source_text,
            source_page=evidence.source_page,
            source_pdf_page=evidence.source_pdf_page,
            source_report_page=evidence.source_report_page,
            source_file_hash=evidence.source_file_hash,
            source_method=evidence.source_method.value,
            bbox=evidence.bbox,
            confidence=evidence.confidence,
            is_kpi_evidence=evidence.is_kpi_evidence,
            quality_flags=[flag.value for flag in evidence.quality_flags],
            needs_ocr_or_vlm=evidence.needs_ocr_or_vlm,
            requires_ocr=evidence.requires_ocr,
            requires_vlm=evidence.requires_vlm,
            ocr_or_vlm_reason=evidence.ocr_or_vlm_reason,
            evidence_preview=evidence.evidence_preview,
            evidence_metadata=evidence.metadata,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._evidence_from_record(record)

    def list_assessments_by_run(self, run_id: str) -> list[DisclosureAssessment]:
        records = self.session.scalars(
            select(AssessmentRecord)
            .where(AssessmentRecord.run_id == run_id)
            .options(selectinload(AssessmentRecord.evidence_items))
            .order_by(AssessmentRecord.assessment_id)
        ).all()
        return [self._assessment_from_record(record) for record in records]

    def get_assessment(self, assessment_id: str) -> DisclosureAssessment | None:
        record = self.session.scalar(
            select(AssessmentRecord)
            .where(AssessmentRecord.assessment_id == assessment_id)
            .options(selectinload(AssessmentRecord.evidence_items))
        )
        return self._assessment_from_record(record) if record is not None else None

    def append_ai_suggestion(
        self,
        suggestion: AIAssessmentSuggestion,
    ) -> AIAssessmentSuggestion:
        record = AIAssessmentSuggestionRecord(
            suggestion_id=suggestion.suggestion_id,
            assessment_id=suggestion.assessment_id,
            run_id=suggestion.run_id,
            status=suggestion.status.value,
            provider=suggestion.provider,
            model=suggestion.model,
            prompt_version=suggestion.prompt_version,
            input_hash=suggestion.input_hash,
            suggested_verdict=(
                suggestion.suggested_verdict.value
                if suggestion.suggested_verdict is not None
                else None
            ),
            rationale_zh=suggestion.rationale_zh,
            missing_items_zh=suggestion.missing_items_zh,
            evidence_ids=suggestion.evidence_ids,
            evidence_pdf_pages=suggestion.evidence_pdf_pages,
            confidence=suggestion.confidence,
            guardrail_codes=suggestion.guardrail_codes,
            usage=suggestion.usage,
            finish_reason=suggestion.finish_reason,
            latency_ms=suggestion.latency_ms,
            retry_count=suggestion.retry_count,
            error_code=suggestion.error_code,
            error_message=suggestion.error_message,
            raw_response=suggestion.raw_response,
            created_at=suggestion.created_at,
        )
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(record)
        return self._ai_suggestion_from_record(record)

    def get_latest_ai_suggestion(
        self,
        assessment_id: str,
    ) -> AIAssessmentSuggestion | None:
        record = self.session.scalar(
            select(AIAssessmentSuggestionRecord)
            .where(AIAssessmentSuggestionRecord.assessment_id == assessment_id)
            .order_by(
                AIAssessmentSuggestionRecord.created_at.desc(),
                AIAssessmentSuggestionRecord.suggestion_id.desc(),
            )
            .limit(1)
        )
        return self._ai_suggestion_from_record(record) if record is not None else None

    def list_ai_suggestions_for_run(
        self,
        run_id: str,
    ) -> list[AIAssessmentSuggestion]:
        records = self.session.scalars(
            select(AIAssessmentSuggestionRecord)
            .where(AIAssessmentSuggestionRecord.run_id == run_id)
            .order_by(
                AIAssessmentSuggestionRecord.created_at,
                AIAssessmentSuggestionRecord.suggestion_id,
            )
        ).all()
        return [self._ai_suggestion_from_record(record) for record in records]

    def latest_review_snapshot(self, assessment_id: str) -> ReviewSnapshot | None:
        record = self.session.scalar(
            select(ReviewSnapshotRecord)
            .where(ReviewSnapshotRecord.assessment_id == assessment_id)
            .order_by(ReviewSnapshotRecord.sequence.desc())
            .limit(1)
        )
        return self._snapshot_from_record(record) if record is not None else None

    def save_review_snapshot(
        self,
        snapshot: ReviewSnapshot,
        changes: list[ReviewChangeEvent],
        *,
        commit: bool = True,
    ) -> ReviewSnapshot:
        record = ReviewSnapshotRecord(
            snapshot_id=snapshot.snapshot_id,
            assessment_id=snapshot.assessment_id,
            run_id=snapshot.run_id,
            sequence=snapshot.sequence,
            previous_snapshot_id=snapshot.previous_snapshot_id,
            operation_type=snapshot.operation_type.value,
            reviewer_name=snapshot.reviewer_name,
            reason_code=snapshot.reason_code,
            reviewer_note=snapshot.reviewer_note,
            reviewed_verdict=snapshot.reviewed_verdict.value if snapshot.reviewed_verdict else None,
            reviewed_applicability_status=(
                snapshot.reviewed_applicability_status.value
                if snapshot.reviewed_applicability_status
                else None
            ),
            evidence_pages=snapshot.evidence_pages,
            evidence_preview=snapshot.evidence_preview,
            rationale=snapshot.rationale,
            missing_items=snapshot.missing_items,
            is_batch_operation=snapshot.is_batch_operation,
            batch_id=snapshot.batch_id,
        )
        self.session.add(record)
        self.session.flush()
        for change in changes:
            self.session.add(
                ReviewChangeEventRecord(
                    snapshot_id=snapshot.snapshot_id,
                    field_name=change.field_name,
                    old_value=change.old_value,
                    new_value=change.new_value,
                )
            )
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        self.session.refresh(record)
        return self._snapshot_from_record(record)

    def list_review_snapshots(self, assessment_id: str) -> list[ReviewSnapshot]:
        records = self.session.scalars(
            select(ReviewSnapshotRecord)
            .where(ReviewSnapshotRecord.assessment_id == assessment_id)
            .order_by(ReviewSnapshotRecord.sequence.desc())
        ).all()
        return [self._snapshot_from_record(record) for record in records]

    def latest_snapshots_for_assessments(self, assessment_ids: list[str]) -> dict[str, ReviewSnapshot]:
        if not assessment_ids:
            return {}
        records = self.session.scalars(
            select(ReviewSnapshotRecord)
            .where(ReviewSnapshotRecord.assessment_id.in_(assessment_ids))
            .order_by(ReviewSnapshotRecord.sequence.desc())
        ).all()
        latest: dict[str, ReviewSnapshot] = {}
        for record in records:
            latest.setdefault(record.assessment_id, self._snapshot_from_record(record))
        return latest

    def list_review_change_events(self, snapshot_id: str) -> list[ReviewChangeEvent]:
        records = self.session.scalars(
            select(ReviewChangeEventRecord)
            .where(ReviewChangeEventRecord.snapshot_id == snapshot_id)
            .order_by(ReviewChangeEventRecord.change_event_id)
        ).all()
        return [
            ReviewChangeEvent(
                change_event_id=record.change_event_id,
                snapshot_id=record.snapshot_id,
                field_name=record.field_name,
                old_value=record.old_value,
                new_value=record.new_value,
                created_at=record.created_at,
            )
            for record in records
        ]

    def save_improvement_action(self, action: ImprovementAction) -> ImprovementAction:
        record = ImprovementActionRecord(
            action_id=action.action_id,
            report_id=action.report_id,
            assessment_id=action.assessment_id,
            title=action.title,
            priority=action.priority.value,
            status=action.status.value,
            owner_name=action.owner_name,
            due_date=action.due_date,
            recommendation_text=action.recommendation_text,
            completion_note=action.completion_note,
            created_by=action.created_by,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._action_from_record(record)

    def list_improvement_actions(self, report_id: str) -> list[ImprovementAction]:
        records = self.session.scalars(
            select(ImprovementActionRecord)
            .where(ImprovementActionRecord.report_id == report_id)
            .order_by(ImprovementActionRecord.created_at.desc())
        ).all()
        return [self._action_from_record(record) for record in records]

    def update_improvement_action(
        self,
        action_id: str,
        *,
        status: ActionStatus | None = None,
        owner_name: str | None = None,
        completion_note: str | None = None,
    ) -> ImprovementAction:
        record = self.session.get(ImprovementActionRecord, action_id)
        if record is None:
            raise ValueError("action not found")
        if status is not None:
            record.status = status.value
        if owner_name is not None:
            record.owner_name = owner_name
        if completion_note is not None:
            record.completion_note = completion_note
        record.updated_at = func.now()
        self.session.commit()
        self.session.refresh(record)
        return self._action_from_record(record)

    def save_export_version(self, export: ExportVersion) -> ExportVersion:
        record = ExportVersionRecord(
            export_id=export.export_id,
            report_id=export.report_id,
            run_id=export.run_id,
            version_number=export.version_number,
            status=export.status,
            is_draft=export.is_draft,
            file_hash=export.file_hash,
            engine_version=export.engine_version,
            risk_rule_version=export.risk_rule_version,
            requirement_version=export.requirement_version,
            review_scope=export.review_scope,
            file_manifest=export.file_manifest,
            supersedes_export_id=export.supersedes_export_id,
            created_by=export.created_by,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._export_from_record(record)

    def list_export_versions(self, report_id: str) -> list[ExportVersion]:
        records = self.session.scalars(
            select(ExportVersionRecord)
            .where(ExportVersionRecord.report_id == report_id)
            .order_by(ExportVersionRecord.created_at.desc(), ExportVersionRecord.export_id.desc())
        ).all()
        return [self._export_from_record(record) for record in records]

    def next_formal_export_version(self, report_id: str) -> int:
        current = self.session.scalar(
            select(func.max(ExportVersionRecord.version_number)).where(
                ExportVersionRecord.report_id == report_id,
                ExportVersionRecord.is_draft.is_(False),
            )
        )
        return int(current or 0) + 1

    def latest_formal_export(self, report_id: str) -> ExportVersion | None:
        record = self.session.scalar(
            select(ExportVersionRecord)
            .where(ExportVersionRecord.report_id == report_id, ExportVersionRecord.is_draft.is_(False))
            .order_by(ExportVersionRecord.version_number.desc())
            .limit(1)
        )
        return self._export_from_record(record) if record else None

    def mark_export_superseded(self, export_id: str) -> None:
        record = self.session.get(ExportVersionRecord, export_id)
        if record:
            record.status = "superseded"
            self.session.commit()

    def save_assessment_risk(
        self,
        risk: AssessmentRisk,
        *,
        commit: bool = True,
    ) -> AssessmentRisk:
        record = AssessmentRiskRecord(
            risk_id=risk.risk_id,
            assessment_id=risk.assessment_id,
            snapshot_id=risk.snapshot_id,
            risk_level=risk.risk_level.value,
            reason_codes=risk.reason_codes,
            risk_rule_version=risk.risk_rule_version,
            evidence_status=risk.evidence_status.value if risk.evidence_status else None,
            applicability_status=(
                risk.applicability_status.value if risk.applicability_status else None
            ),
            trigger_event=risk.trigger_event,
        )
        self.session.add(record)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        self.session.refresh(record)
        return self._risk_from_record(record)

    def new_risk_id(self) -> str:
        return new_id("risk")

    def new_export_id(self) -> str:
        return new_id("export")

    def latest_risks_for_assessments(self, assessment_ids: list[str]) -> dict[str, AssessmentRisk]:
        if not assessment_ids:
            return {}
        records = self.session.scalars(
            select(AssessmentRiskRecord)
            .where(AssessmentRiskRecord.assessment_id.in_(assessment_ids))
            .order_by(AssessmentRiskRecord.calculated_at.desc(), AssessmentRiskRecord.risk_id.desc())
        ).all()
        latest: dict[str, AssessmentRisk] = {}
        for record in records:
            latest.setdefault(record.assessment_id, self._risk_from_record(record))
        return latest

    def latest_run_for_report(self, report_id: str) -> AnalysisRun | None:
        record = self.session.scalar(
            select(AnalysisRunRecord)
            .where(AnalysisRunRecord.report_id == report_id)
            .order_by(AnalysisRunRecord.started_at.desc().nullslast(), AnalysisRunRecord.run_id.desc())
            .limit(1)
        )
        return self._run_from_record(record) if record is not None else None

    def save_review_decision(self, decision: ReviewDecision) -> ReviewDecision:
        record = ReviewDecisionRecord(
            decision_id=decision.decision_id,
            run_id=decision.run_id,
            assessment_id=decision.assessment_id,
            review_status=decision.review_status.value,
            reviewer_note=decision.reviewer_note,
            decided_at=decision.decided_at,
        )
        self.session.add(record)
        assessment = self.session.get(AssessmentRecord, decision.assessment_id)
        if assessment is not None:
            assessment.review_status = decision.review_status.value
        self.session.commit()
        self.session.refresh(record)
        return ReviewDecision(
            decision_id=record.decision_id,
            run_id=record.run_id,
            assessment_id=record.assessment_id,
            review_status=ReviewStatus(record.review_status),
            reviewer_note=record.reviewer_note,
            decided_at=record.decided_at,
        )

    def create_audit_event(
        self,
        run_id: str | None,
        event_type: str,
        payload: dict,
        *,
        commit: bool = True,
    ) -> None:
        self.session.add(
            AuditEventRecord(
                run_id=run_id,
                event_type=event_type,
                event_payload=payload,
            )
        )
        if commit:
            self.session.commit()
        else:
            self.session.flush()

    def count_audit_events(self, run_id: str) -> int:
        return len(self.session.scalars(select(AuditEventRecord).where(AuditEventRecord.run_id == run_id)).all())
    def list_audit_runs(self) -> list[dict]:
        rows = self.session.execute(
            select(AnalysisRunRecord, ReportRecord)
            .join(ReportRecord, ReportRecord.report_id == AnalysisRunRecord.report_id)
            .order_by(AnalysisRunRecord.run_id)
        ).all()
        audit_runs = []
        for run_record, report_record in rows:
            run_event_records = self.session.scalars(
                select(AuditEventRecord)
                .where(AuditEventRecord.run_id == run_record.run_id)
                .order_by(AuditEventRecord.audit_event_id)
            ).all()
            report_event_records = [
                event
                for event in self.session.scalars(
                    select(AuditEventRecord)
                    .where(AuditEventRecord.run_id.is_(None))
                    .order_by(AuditEventRecord.audit_event_id)
                ).all()
                if event.event_payload.get("report_id") == report_record.report_id
            ]
            event_records = sorted(
                [*report_event_records, *run_event_records],
                key=lambda event: event.audit_event_id,
            )
            audit_runs.append(
                {
                    "run_id": run_record.run_id,
                    "report_id": run_record.report_id,
                    "original_filename": report_record.original_filename,
                    "file_hash": report_record.file_hash,
                    "status": run_record.status,
                    "model_called": run_record.confirm_llm,
                    "started_at": run_record.started_at.isoformat() if run_record.started_at else None,
                    "completed_at": run_record.completed_at.isoformat() if run_record.completed_at else None,
                    "error_message": run_record.error_message,
                    "events": [
                        {
                            "audit_event_id": event.audit_event_id,
                            "event_type": event.event_type,
                            "payload": event.event_payload,
                            "created_at": event.created_at.isoformat() if event.created_at else None,
                        }
                        for event in event_records
                    ],
                }
            )
        return audit_runs

    def save_pages_and_chunks(self, pages: list[PageExtraction], chunks: list[DocumentChunk]) -> None:
        report_ids = sorted(
            {page.report_id for page in pages} | {chunk.report_id for chunk in chunks}
        )
        if report_ids:
            self.session.execute(
                delete(DocumentChunkRecord).where(DocumentChunkRecord.report_id.in_(report_ids))
            )
            self.session.execute(
                delete(DocumentPageRecord).where(DocumentPageRecord.report_id.in_(report_ids))
            )
            self.session.flush()
        for page in pages:
            self.session.add(
                DocumentPageRecord(
                    report_id=page.report_id,
                    page_number=page.page_number,
                    text=page.text,
                    image_count=page.image_count,
                    table_count=page.table_count,
                    quality_flags=[flag.value for flag in page.quality_flags],
                    source_method=page.source_method.value,
                    page_metadata=page.metadata,
                )
            )
        for chunk in chunks:
            self.session.add(
                DocumentChunkRecord(
                    chunk_id=chunk.chunk_id,
                    report_id=chunk.report_id,
                    text=chunk.text,
                    source_page=chunk.source_page,
                    source_method=chunk.source_method.value,
                    source_file_hash=chunk.source_file_hash,
                    bbox=chunk.bbox,
                    quality_flags=[flag.value for flag in chunk.quality_flags],
                    embedding_status=chunk.embedding_status,
                    embedding_model=chunk.embedding_model,
                    embedding_dim=chunk.embedding_dim,
                    chunk_metadata=chunk.metadata,
                )
            )
        self.session.commit()

    def save_disclosure_task(self, task: DisclosureTask) -> DisclosureTask:
        self.session.add(
            DisclosureTaskRecord(
                task_id=task.task_id,
                run_id=task.run_id,
                report_id=task.report_id,
                standard_id=task.standard_id,
                standard_version=task.standard_version,
                disclosure_id=task.disclosure_id,
                requirement_id=task.requirement_id,
                requirement_text=task.requirement_text,
                source_requirement_text=task.source_requirement_text,
                context_requirement_ids=task.context_requirement_ids,
                structure_status=task.structure_status,
                keywords=task.keywords,
            )
        )
        self.session.commit()
        return task

    def save_recommendation(self, recommendation: Recommendation) -> Recommendation:
        record = RecommendationRecord(
            recommendation_id=recommendation.recommendation_id,
            run_id=recommendation.run_id,
            report_id=recommendation.report_id,
            disclosure_id=recommendation.disclosure_id,
            requirement_id=recommendation.requirement_id,
            recommendation_text=recommendation.recommendation_text,
            created_at=recommendation.created_at,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return Recommendation(
            recommendation_id=record.recommendation_id,
            run_id=record.run_id,
            report_id=record.report_id,
            disclosure_id=record.disclosure_id,
            requirement_id=record.requirement_id,
            recommendation_text=record.recommendation_text,
            created_at=record.created_at,
        )
    def _recommendation_from_record(self, record: RecommendationRecord) -> Recommendation:
        return Recommendation(
            recommendation_id=record.recommendation_id,
            run_id=record.run_id,
            report_id=record.report_id,
            disclosure_id=record.disclosure_id,
            requirement_id=record.requirement_id,
            recommendation_text=record.recommendation_text,
            created_at=record.created_at,
        )

    def _review_decision_from_record(self, record: ReviewDecisionRecord) -> ReviewDecision:
        return ReviewDecision(
            decision_id=record.decision_id,
            run_id=record.run_id,
            assessment_id=record.assessment_id,
            review_status=ReviewStatus(record.review_status),
            reviewer_note=record.reviewer_note,
            decided_at=record.decided_at,
        )
    def _report_from_record(self, record: ReportRecord) -> Report:
        return Report(
            report_id=record.report_id,
            original_filename=record.original_filename,
            stored_path=record.stored_path,
            file_hash=record.file_hash,
            page_count=record.page_count,
            company_name=record.company_name,
            report_year=record.report_year,
            language=record.language,
            status=ReportStatus(record.status),
            metadata_detected=record.metadata_detected,
            metadata_confirmed_at=record.metadata_confirmed_at,
            updated_at=record.updated_at,
            reopened_at=record.reopened_at,
            reopen_reason=record.reopen_reason,
            created_at=record.created_at,
        )

    def _run_from_record(self, record: AnalysisRunRecord) -> AnalysisRun:
        return AnalysisRun(
            run_id=record.run_id,
            report_id=record.report_id,
            status=RunStatus(record.status),
            confirm_llm=record.confirm_llm,
            started_at=record.started_at,
            completed_at=record.completed_at,
            error_message=record.error_message,
            parent_run_id=record.parent_run_id,
            engine_version=record.engine_version,
            risk_rule_version=record.risk_rule_version,
            standard_unit_count=(
                record.standard_unit_count
                if record.standard_unit_count is not None
                else record.eligible_requirement_count
            ),
            eligible_requirement_count=record.eligible_requirement_count,
            context_only_count=record.context_only_count or 0,
            method_pending_count=record.method_pending_count or 0,
            succeeded_requirement_count=record.succeeded_requirement_count,
            failed_requirement_count=record.failed_requirement_count,
            failure_summary=record.failure_summary,
        )

    def _stage_event_from_record(self, record: AnalysisStageEventRecord) -> AnalysisStageEvent:
        return AnalysisStageEvent(
            stage_event_id=record.stage_event_id,
            run_id=record.run_id,
            stage_code=record.stage_code,
            status=record.status,
            completed_units=record.completed_units,
            total_units=record.total_units,
            error_summary=record.error_summary,
            created_at=record.created_at,
        )

    def _risk_from_record(self, record: AssessmentRiskRecord) -> AssessmentRisk:
        return AssessmentRisk(
            risk_id=record.risk_id,
            assessment_id=record.assessment_id,
            snapshot_id=record.snapshot_id,
            risk_level=RiskLevel(record.risk_level),
            reason_codes=record.reason_codes,
            risk_rule_version=record.risk_rule_version,
            evidence_status=(
                EvidenceStatus(record.evidence_status) if record.evidence_status else None
            ),
            applicability_status=(
                ApplicabilityStatus(record.applicability_status)
                if record.applicability_status
                else None
            ),
            trigger_event=record.trigger_event,
            calculated_at=record.calculated_at,
        )

    def _ai_suggestion_from_record(
        self,
        record: AIAssessmentSuggestionRecord,
    ) -> AIAssessmentSuggestion:
        return AIAssessmentSuggestion(
            suggestion_id=record.suggestion_id,
            assessment_id=record.assessment_id,
            run_id=record.run_id,
            status=AISuggestionStatus(record.status),
            provider=record.provider,
            model=record.model,
            prompt_version=record.prompt_version,
            input_hash=record.input_hash,
            suggested_verdict=(
                AssessmentVerdict(record.suggested_verdict)
                if record.suggested_verdict
                else None
            ),
            rationale_zh=record.rationale_zh,
            missing_items_zh=record.missing_items_zh,
            evidence_ids=record.evidence_ids,
            evidence_pdf_pages=record.evidence_pdf_pages,
            confidence=record.confidence,
            guardrail_codes=record.guardrail_codes,
            usage=record.usage,
            finish_reason=record.finish_reason,
            latency_ms=record.latency_ms,
            retry_count=record.retry_count,
            error_code=record.error_code,
            error_message=record.error_message,
            raw_response=record.raw_response,
            created_at=record.created_at,
        )

    def _snapshot_from_record(self, record: ReviewSnapshotRecord) -> ReviewSnapshot:
        return ReviewSnapshot(
            snapshot_id=record.snapshot_id,
            assessment_id=record.assessment_id,
            run_id=record.run_id,
            sequence=record.sequence,
            previous_snapshot_id=record.previous_snapshot_id,
            operation_type=ReviewOperation(record.operation_type),
            reviewer_name=record.reviewer_name,
            reason_code=record.reason_code,
            reviewer_note=record.reviewer_note,
            reviewed_verdict=AssessmentVerdict(record.reviewed_verdict) if record.reviewed_verdict else None,
            reviewed_applicability_status=(
                ApplicabilityStatus(record.reviewed_applicability_status)
                if record.reviewed_applicability_status
                else None
            ),
            evidence_pages=record.evidence_pages,
            evidence_preview=record.evidence_preview,
            rationale=record.rationale,
            missing_items=record.missing_items,
            is_batch_operation=record.is_batch_operation,
            batch_id=record.batch_id,
            created_at=record.created_at,
        )

    def _action_from_record(self, record: ImprovementActionRecord) -> ImprovementAction:
        return ImprovementAction(
            action_id=record.action_id,
            report_id=record.report_id,
            assessment_id=record.assessment_id,
            title=record.title,
            priority=ActionPriority(record.priority),
            status=ActionStatus(record.status),
            owner_name=record.owner_name,
            due_date=record.due_date,
            recommendation_text=record.recommendation_text,
            completion_note=record.completion_note,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _export_from_record(self, record: ExportVersionRecord) -> ExportVersion:
        return ExportVersion(
            export_id=record.export_id,
            report_id=record.report_id,
            run_id=record.run_id,
            version_number=record.version_number,
            status=record.status,
            is_draft=record.is_draft,
            file_hash=record.file_hash,
            engine_version=record.engine_version,
            risk_rule_version=record.risk_rule_version,
            requirement_version=record.requirement_version,
            review_scope=record.review_scope,
            file_manifest=record.file_manifest,
            supersedes_export_id=record.supersedes_export_id,
            created_by=record.created_by,
            created_at=record.created_at,
        )

    def _assessment_from_record(self, record: AssessmentRecord) -> DisclosureAssessment:
        evidence = [self._evidence_from_record(item) for item in record.evidence_items]
        return DisclosureAssessment(
            assessment_id=record.assessment_id,
            run_id=record.run_id,
            report_id=record.report_id,
            standard_id=record.standard_id,
            standard_version=record.standard_version,
            disclosure_id=record.disclosure_id,
            requirement_id=record.requirement_id,
            verdict=AssessmentVerdict(record.verdict),
            rationale=record.rationale,
            evidence=evidence,
            missing_items=record.missing_items,
            model_called=record.model_called,
            review_status=ReviewStatus(record.review_status),
        )

    def _evidence_from_record(self, record: EvidenceItemRecord) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=record.evidence_id,
            run_id=record.run_id,
            report_id=record.report_id,
            source_text=record.source_text,
            source_page=record.source_page,
            source_pdf_page=record.source_pdf_page,
            source_report_page=record.source_report_page,
            source_file_hash=record.source_file_hash,
            source_method=EvidenceSourceMethod(record.source_method),
            bbox=record.bbox,
            confidence=record.confidence,
            is_kpi_evidence=record.is_kpi_evidence,
            quality_flags=[PageQualityFlag(flag) for flag in record.quality_flags],
            needs_ocr_or_vlm=record.needs_ocr_or_vlm,
            requires_ocr=record.requires_ocr,
            requires_vlm=record.requires_vlm,
            ocr_or_vlm_reason=record.ocr_or_vlm_reason,
            evidence_preview=record.evidence_preview,
            metadata=record.evidence_metadata,
        )


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"
