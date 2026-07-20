from typing import Any

from src.db.repositories import Repository, new_id
from src.domain.enums import ApplicabilityStatus, AssessmentVerdict, ReportStatus, ReviewOperation, RiskLevel
from src.domain.models import ReviewChangeEvent, ReviewSnapshot
from src.services.risk_service import calculate_and_store_risk


class ReviewService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def record(
        self,
        assessment_id: str,
        *,
        operation_type: ReviewOperation,
        reviewer_name: str,
        reason_code: str,
        reviewer_note: str = "",
        reviewed_verdict: AssessmentVerdict | None = None,
        reviewed_applicability_status: ApplicabilityStatus | None = None,
        evidence_pages: list[int] | None = None,
        evidence_preview: str | None = None,
        rationale: str | None = None,
        missing_items: list[str] | None = None,
        expected_previous_snapshot_id: str | None = None,
        is_batch_operation: bool = False,
        batch_id: str | None = None,
        advance_report_status: bool = True,
        commit: bool = True,
    ) -> ReviewSnapshot:
        assessment = self.repository.get_assessment(assessment_id)
        if assessment is None:
            raise LookupError("assessment not found")
        latest = self.repository.latest_review_snapshot(assessment_id)
        if expected_previous_snapshot_id is not None and (
            latest is None or latest.snapshot_id != expected_previous_snapshot_id
        ):
            raise RuntimeError("snapshot conflict")
        if operation_type in {ReviewOperation.MODIFY, ReviewOperation.INVALIDATE_EVIDENCE, ReviewOperation.REOPEN} and not reviewer_note.strip():
            raise ValueError("reviewer_note is required")
        overrides = [
            reviewed_verdict,
            reviewed_applicability_status,
            evidence_pages,
            evidence_preview,
            rationale,
            missing_items,
        ]
        if operation_type is ReviewOperation.MODIFY and all(value is None for value in overrides):
            raise ValueError("modify requires at least one changed field")

        previous_values = self._effective_values(assessment, latest)
        values = dict(previous_values)
        supplied = {
            "reviewed_verdict": reviewed_verdict,
            "reviewed_applicability_status": reviewed_applicability_status,
            "evidence_pages": evidence_pages,
            "evidence_preview": evidence_preview,
            "rationale": rationale,
            "missing_items": missing_items,
        }
        for field, value in supplied.items():
            if value is not None:
                values[field] = value
        if operation_type is ReviewOperation.APPROVE and values["reviewed_verdict"] is None:
            values["reviewed_verdict"] = assessment.verdict

        snapshot_id = new_id("snapshot")
        snapshot = ReviewSnapshot(
            snapshot_id=snapshot_id,
            assessment_id=assessment_id,
            run_id=assessment.run_id,
            sequence=(latest.sequence + 1) if latest else 1,
            previous_snapshot_id=latest.snapshot_id if latest else None,
            operation_type=operation_type,
            reviewer_name=reviewer_name.strip(),
            reason_code=reason_code,
            reviewer_note=reviewer_note,
            reviewed_verdict=values["reviewed_verdict"],
            reviewed_applicability_status=values["reviewed_applicability_status"],
            evidence_pages=values["evidence_pages"],
            evidence_preview=values["evidence_preview"],
            rationale=values["rationale"],
            missing_items=values["missing_items"],
            is_batch_operation=is_batch_operation,
            batch_id=batch_id,
        )
        changes = [
            ReviewChangeEvent(
                snapshot_id=snapshot_id,
                field_name=field,
                old_value=self._json_value(previous_values[field]),
                new_value=self._json_value(value),
            )
            for field, value in values.items()
            if self._json_value(previous_values[field]) != self._json_value(value)
        ]
        saved = (
            self.repository.save_review_snapshot(snapshot, changes)
            if commit
            else self.repository.save_review_snapshot(
                snapshot,
                changes,
                commit=False,
            )
        )
        effective = assessment.model_copy(
            update={
                "verdict": values["reviewed_verdict"] or assessment.verdict,
                "rationale": values["rationale"] or assessment.rationale,
                "missing_items": values["missing_items"] if values["missing_items"] is not None else assessment.missing_items,
                "evidence": [] if operation_type is ReviewOperation.INVALIDATE_EVIDENCE else assessment.evidence,
            }
        )
        run = self.repository.get_run(assessment.run_id)
        risk_rule_version = run.risk_rule_version if run else "risk-v1"
        risk_kwargs = {
            "trigger_event": f"review_{operation_type.value}",
            "snapshot_id": saved.snapshot_id,
            "risk_rule_version": risk_rule_version,
            "applicability_status": values["reviewed_applicability_status"],
            "evidence_invalidated": operation_type
            is ReviewOperation.INVALIDATE_EVIDENCE,
            "reopened": operation_type is ReviewOperation.REOPEN,
        }
        if not commit:
            risk_kwargs["commit"] = False
        calculate_and_store_risk(self.repository, effective, **risk_kwargs)
        if advance_report_status:
            if operation_type is ReviewOperation.REOPEN:
                if commit:
                    self.repository.update_report_status(
                        assessment.report_id,
                        ReportStatus.REOPENED,
                    )
                else:
                    self.repository.update_report_status(
                        assessment.report_id,
                        ReportStatus.REOPENED,
                        commit=False,
                    )
            else:
                if commit:
                    self._advance_report_status(
                        assessment.report_id,
                        assessment.run_id,
                    )
                else:
                    self._advance_report_status(
                        assessment.report_id,
                        assessment.run_id,
                        commit=False,
                    )
        return saved

    def record_applicability_batch(
        self,
        report_id: str,
        *,
        assessment_ids: list[str],
        reviewed_applicability_status: ApplicabilityStatus,
        reviewer_name: str,
        reviewer_note: str,
    ) -> tuple[str, list[ReviewSnapshot]]:
        if reviewed_applicability_status not in {
            ApplicabilityStatus.APPLICABLE,
            ApplicabilityStatus.NOT_APPLICABLE_CONFIRMED,
        }:
            raise ValueError(
                "batch applicability decision must be applicable or confirmed not applicable"
            )
        if not reviewer_name.strip():
            raise ValueError("reviewer_name is required")
        if not reviewer_note.strip():
            raise ValueError("reviewer_note is required")
        if not assessment_ids:
            raise ValueError("assessment_ids is required")
        if len(set(assessment_ids)) != len(assessment_ids):
            raise ValueError("assessment_ids contains duplicates")
        if self.repository.get_report(report_id) is None:
            raise LookupError("report not found")
        run = self.repository.latest_run_for_report(report_id)
        if run is None:
            raise LookupError("report has no analysis run")

        assessments = []
        for assessment_id in assessment_ids:
            assessment = self.repository.get_assessment(assessment_id)
            if (
                assessment is None
                or assessment.report_id != report_id
                or assessment.run_id != run.run_id
            ):
                raise ValueError(
                    f"assessment is not in the latest report run: {assessment_id}"
                )
            assessments.append(assessment)
        risks = self.repository.latest_risks_for_assessments(assessment_ids)
        stale_ids = [
            assessment.assessment_id
            for assessment in assessments
            if assessment.assessment_id not in risks
            or risks[assessment.assessment_id].applicability_status
            is not ApplicabilityStatus.UNDETERMINED
        ]
        if stale_ids:
            raise RuntimeError(
                "applicability decision conflict: " + ", ".join(stale_ids)
            )

        batch_id = new_id("batch")
        try:
            snapshots = [
                self.record(
                    assessment.assessment_id,
                    operation_type=ReviewOperation.MODIFY,
                    reviewer_name=reviewer_name,
                    reason_code="applicability_batch_reviewed",
                    reviewer_note=reviewer_note,
                    reviewed_applicability_status=reviewed_applicability_status,
                    is_batch_operation=True,
                    batch_id=batch_id,
                    advance_report_status=False,
                    commit=False,
                )
                for assessment in assessments
            ]
            self._advance_report_status(report_id, run.run_id, commit=False)
            self.repository.create_audit_event(
                run.run_id,
                "applicability_batch_reviewed",
                {
                    "batch_id": batch_id,
                    "assessment_count": len(snapshots),
                    "reviewed_applicability_status": reviewed_applicability_status.value,
                },
                commit=False,
            )
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            raise
        return batch_id, snapshots

    def _advance_report_status(
        self,
        report_id: str,
        run_id: str,
        *,
        commit: bool = True,
    ) -> None:
        assessments = self.repository.list_assessments_by_run(run_id)
        assessment_ids = [item.assessment_id for item in assessments]
        risks = self.repository.latest_risks_for_assessments(assessment_ids)
        snapshots = self.repository.latest_snapshots_for_assessments(assessment_ids)
        high_risk_ids = [
            item.assessment_id
            for item in assessments
            if item.assessment_id not in risks or risks[item.assessment_id].risk_level is RiskLevel.HIGH
        ]
        reviewed_operations = {
            ReviewOperation.APPROVE,
            ReviewOperation.MODIFY,
            ReviewOperation.LEGACY_IMPORT,
        }
        if all(
            assessment_id in snapshots
            and snapshots[assessment_id].operation_type in reviewed_operations
            for assessment_id in high_risk_ids
        ):
            if commit:
                self.repository.update_report_status(
                    report_id,
                    ReportStatus.HIGH_RISK_REVIEW_COMPLETED,
                )
            else:
                self.repository.update_report_status(
                    report_id,
                    ReportStatus.HIGH_RISK_REVIEW_COMPLETED,
                    commit=False,
                )

    @staticmethod
    def _effective_values(assessment, latest: ReviewSnapshot | None) -> dict[str, Any]:
        return {
            "reviewed_verdict": latest.reviewed_verdict if latest else None,
            "reviewed_applicability_status": (
                latest.reviewed_applicability_status if latest else None
            ),
            "evidence_pages": latest.evidence_pages if latest else None,
            "evidence_preview": latest.evidence_preview if latest else None,
            "rationale": latest.rationale if latest else assessment.rationale,
            "missing_items": latest.missing_items if latest else assessment.missing_items,
        }

    @staticmethod
    def _json_value(value):
        return (
            value.value
            if isinstance(value, (AssessmentVerdict, ApplicabilityStatus))
            else value
        )
