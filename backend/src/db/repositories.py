from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.db.models import (
    AnalysisRunRecord,
    DisclosureTaskRecord,
    DocumentChunkRecord,
    DocumentPageRecord,
    AssessmentRecord,
    AuditEventRecord,
    EvidenceItemRecord,
    RecommendationRecord,
    ReportRecord,
    ReviewDecisionRecord,
)
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus, RunStatus
from src.domain.models import AnalysisRun, DisclosureAssessment, DisclosureTask, DocumentChunk, EvidenceItem, PageExtraction, Recommendation, Report, ReviewDecision


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def create_report(self, report: Report) -> Report:
        record = ReportRecord(
            report_id=report.report_id,
            original_filename=report.original_filename,
            stored_path=report.stored_path,
            file_hash=report.file_hash,
            page_count=report.page_count,
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

    def create_run(self, run: AnalysisRun) -> AnalysisRun:
        record = AnalysisRunRecord(
            run_id=run.run_id,
            report_id=run.report_id,
            status=run.status.value,
            confirm_llm=run.confirm_llm,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._run_from_record(record)

    def update_run_status(self, run_id: str, status: RunStatus, error_message: str | None = None) -> AnalysisRun:
        record = self.session.get(AnalysisRunRecord, run_id)
        if record is None:
            raise ValueError(f"run not found: {run_id}")
        record.status = status.value
        record.error_message = error_message
        self.session.commit()
        self.session.refresh(record)
        return self._run_from_record(record)

    def list_runs(self) -> list[AnalysisRun]:
        records = self.session.scalars(select(AnalysisRunRecord).order_by(AnalysisRunRecord.run_id)).all()
        return [self._run_from_record(record) for record in records]
    def get_run(self, run_id: str) -> AnalysisRun | None:
        record = self.session.get(AnalysisRunRecord, run_id)
        if record is None:
            return None
        return self._run_from_record(record)

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

    def create_audit_event(self, run_id: str | None, event_type: str, payload: dict) -> None:
        self.session.add(
            AuditEventRecord(
                run_id=run_id,
                event_type=event_type,
                event_payload=payload,
            )
        )
        self.session.commit()

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
