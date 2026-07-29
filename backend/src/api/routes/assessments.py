from collections import Counter
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.schemas import (
    AssessmentDetailResponse,
    AssessmentListResponse,
    ReportDashboardResponse,
    RequirementScopeListResponse,
)
from src.db.repositories import Repository
from src.db.session import get_db_session
from src.domain.enums import (
    ApplicabilityStatus,
    AssessmentVerdict,
    RiskLevel,
)
from src.services.analysis_runner import GRI_REQUIREMENTS_PATH
from src.services.effective_run_view_service import EffectiveRunViewService
from src.services.presentation_localization import localize_missing_items, localize_rationale
from src.services.requirement_scope_service import RequirementScopeService
from src.standards.gri import GRIAdapter


router = APIRouter(prefix="/api/reports/{report_id}", tags=["assessments"])


def _topic(requirement_id: str) -> str:
    parts = requirement_id.split("-")
    return parts[0] if len(parts) < 2 else "-".join(parts[:2])


def _review_status(snapshot) -> str:
    if snapshot is None:
        return "pending_review"
    return {
        "approve": "reviewed_approved",
        "modify": "reviewed_modified",
        "invalidate_evidence": "evidence_invalidated",
        "reopen": "reopened",
        "legacy_import": "reviewed_approved",
    }.get(snapshot.operation_type.value, "pending_review")


def _requirement_sort_key(requirement_id: str) -> tuple:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", requirement_id)
        if part
    )


def _paginate(items: list[dict], *, page: int, page_size: int) -> dict:
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def filter_scope_items(
    items: list[dict],
    *,
    query: str | None,
    unit_status: str | None,
    effective_verdict: str | None,
    review_priority: str | None,
    review_status: str | None,
    applicability_status: str | None,
) -> list[dict]:
    normalized_query = (query or "").strip().casefold()
    filtered = []
    for item in items:
        if normalized_query:
            searchable_values = [
                item.get("requirement_id"),
                item.get("gri_topic"),
                item.get("source_requirement_text"),
                item.get("effective_requirement_text"),
                *(item.get("component_requirement_ids") or []),
                *(item.get("incorporated_into_requirement_ids") or []),
            ]
            haystack = "\n".join(
                str(value).casefold()
                for value in searchable_values
                if value is not None
            )
            if normalized_query not in haystack:
                continue
        expected = {
            "unit_status": unit_status,
            "effective_verdict": effective_verdict,
            "review_priority": review_priority,
            "review_status": review_status,
            "applicability_status": applicability_status,
        }
        if any(
            value is not None and item.get(field) != value
            for field, value in expected.items()
        ):
            continue
        filtered.append(item)
    return filtered


def _item(assessment, risk, snapshot=None) -> dict:
    source_pages = sorted({item.source_pdf_page or item.source_page for item in assessment.evidence})
    review_priority = risk.risk_level.value if risk else RiskLevel.HIGH.value
    return {
        "assessment_id": assessment.assessment_id,
        "requirement_id": assessment.requirement_id,
        "requirement_name_zh": assessment.requirement_id,
        "gri_topic": _topic(assessment.requirement_id),
        "system_verdict": assessment.verdict.value,
        "reviewed_verdict": snapshot.reviewed_verdict.value if snapshot and snapshot.reviewed_verdict else None,
        "effective_verdict": snapshot.reviewed_verdict.value if snapshot and snapshot.reviewed_verdict else assessment.verdict.value,
        "risk_level": review_priority,
        "review_priority": review_priority,
        "evidence_status": risk.evidence_status.value if risk and risk.evidence_status else None,
        "applicability_status": (
            risk.applicability_status.value if risk and risk.applicability_status else None
        ),
        "risk_reason_codes": risk.reason_codes if risk else ["risk_not_calculated"],
        "review_status": _review_status(snapshot),
        "evidence_count": len(assessment.evidence),
        "source_pdf_pages": source_pages,
        "action_status": None,
    }


def _report_assessments(repo: Repository, report_id: str):
    latest_run = repo.latest_run_for_report(report_id)
    if latest_run is None:
        return None, [], {}, {}, 0
    if not _uses_frozen_independent_scope(repo, latest_run):
        assessments = repo.list_assessments_by_run(latest_run.run_id)
        assessments.sort(
            key=lambda item: (
                _requirement_sort_key(item.requirement_id),
                item.assessment_id,
            )
        )
        ids = [item.assessment_id for item in assessments]
        return (
            latest_run,
            assessments,
            repo.latest_risks_for_assessments(ids),
            repo.latest_snapshots_for_assessments(ids),
            latest_run.failed_requirement_count,
        )

    adapter = GRIAdapter(GRI_REQUIREMENTS_PATH)
    independent_ids = {
        requirement.requirement_id
        for requirement in adapter.load_requirements()
    }
    effective_view = EffectiveRunViewService(repo).build(
        report_id=report_id,
        independent_requirement_ids=independent_ids,
    )
    run = effective_view.latest_run
    assessments = [
        effective.assessment
        for effective in effective_view.assessments_by_requirement.values()
    ]
    assessments.sort(
        key=lambda item: (
            _requirement_sort_key(item.requirement_id),
            item.assessment_id,
        )
    )
    ids = [item.assessment_id for item in assessments]
    risks = repo.latest_risks_for_assessments(ids)
    snapshots = repo.latest_snapshots_for_assessments(ids)
    return (
        run,
        assessments,
        risks,
        snapshots,
        len(effective_view.failed_requirement_ids),
    )


def _uses_frozen_independent_scope(repo: Repository, latest_run) -> bool:
    return EffectiveRunViewService(repo).lineage_contains_eligible_count(
        latest_run=latest_run,
        eligible_count=499,
    )


@router.get("/dashboard", response_model=ReportDashboardResponse)
def dashboard(report_id: str, session: Session = Depends(get_db_session)) -> dict:
    repo = Repository(session)
    if repo.get_report(report_id) is None:
        raise HTTPException(status_code=404, detail="report not found")
    scope_service = RequirementScopeService(repo, GRIAdapter(GRI_REQUIREMENTS_PATH))
    run, assessments, risks, snapshots, failed_count = _report_assessments(
        repo,
        report_id,
    )
    risk_counts = Counter((risks.get(item.assessment_id).risk_level.value if risks.get(item.assessment_id) else "high") for item in assessments)
    review_priority_counts = Counter(risk_counts)
    if failed_count:
        review_priority_counts[RiskLevel.HIGH.value] += failed_count
    applicability_counts = Counter(
        risks[item.assessment_id].applicability_status.value
        for item in assessments
        if risks.get(item.assessment_id)
        and risks[item.assessment_id].applicability_status is not None
    )
    verdict_counts = Counter(item.verdict.value for item in assessments)
    high_items = [item for item in assessments if not risks.get(item.assessment_id) or risks[item.assessment_id].risk_level is RiskLevel.HIGH]
    reviewed = sum(
        snapshots.get(item.assessment_id) is not None
        and snapshots[item.assessment_id].operation_type.value in {"approve", "modify", "legacy_import"}
        for item in high_items
    )
    high_total = len(high_items) + failed_count
    return {
        "report_id": report_id,
        "run_id": run.run_id if run else None,
        "standard_unit_count": scope_service.scope_summary()["standard_unit_count"],
        "verdict_counts": dict(verdict_counts),
        "risk_counts": dict(risk_counts),
        "review_priority_counts": dict(review_priority_counts),
        "high_risk_total": high_total,
        "high_risk_reviewed": reviewed,
        "high_priority_total": high_total,
        "high_priority_reviewed": reviewed,
        "high_priority_unresolved": high_total - reviewed,
        "applicability_counts": dict(applicability_counts),
        "applicability_undetermined_total": applicability_counts.get(
            ApplicabilityStatus.UNDETERMINED.value,
            0,
        ),
        "failed_requirement_count": failed_count,
    }


@router.get("/scope-items", response_model=RequirementScopeListResponse)
def list_scope_items(
    report_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    query: str | None = Query(default=None, max_length=100),
    unit_status: Literal[
        "assessed",
        "context_incorporated",
    ]
    | None = None,
    effective_verdict: AssessmentVerdict | None = None,
    review_priority: RiskLevel | None = None,
    review_status: Literal[
        "pending_review",
        "reviewed_approved",
        "reviewed_modified",
        "evidence_invalidated",
        "reopened",
    ]
    | None = None,
    applicability_status: ApplicabilityStatus | None = None,
    session: Session = Depends(get_db_session),
) -> dict:
    repo = Repository(session)
    if repo.get_report(report_id) is None:
        raise HTTPException(status_code=404, detail="report not found")
    service = RequirementScopeService(repo, GRIAdapter(GRI_REQUIREMENTS_PATH))
    try:
        items = service.list_items(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    items = filter_scope_items(
        items,
        query=query,
        unit_status=unit_status,
        effective_verdict=(
            effective_verdict.value if effective_verdict else None
        ),
        review_priority=(
            review_priority.value if review_priority else None
        ),
        review_status=review_status,
        applicability_status=(
            applicability_status.value if applicability_status else None
        ),
    )
    return _paginate(items, page=page, page_size=page_size)


@router.get("/assessments", response_model=AssessmentListResponse)
def list_assessments(
    report_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    risk_level: RiskLevel | None = None,
    review_priority: RiskLevel | None = None,
    applicability_status: ApplicabilityStatus | None = None,
    session: Session = Depends(get_db_session),
) -> dict:
    repo = Repository(session)
    if repo.get_report(report_id) is None:
        raise HTTPException(status_code=404, detail="report not found")
    if risk_level is not None and review_priority is not None and risk_level is not review_priority:
        raise HTTPException(
            status_code=422,
            detail="risk_level and review_priority filters conflict",
        )
    effective_priority = review_priority or risk_level
    _, assessments, risks, snapshots, _ = _report_assessments(repo, report_id)
    items = [_item(item, risks.get(item.assessment_id), snapshots.get(item.assessment_id)) for item in assessments]
    if effective_priority is not None:
        items = [
            item
            for item in items
            if item["review_priority"] == effective_priority.value
        ]
    if applicability_status is not None:
        items = [
            item
            for item in items
            if item["applicability_status"] == applicability_status.value
        ]
    return _paginate(items, page=page, page_size=page_size)


@router.get("/review-queue", response_model=AssessmentListResponse)
def review_queue(
    report_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> dict:
    repo = Repository(session)
    if repo.get_report(report_id) is None:
        raise HTTPException(status_code=404, detail="report not found")
    _, assessments, risks, snapshots, _ = _report_assessments(repo, report_id)
    items = [
        _item(item, risks.get(item.assessment_id), snapshots.get(item.assessment_id))
        for item in assessments
    ]
    unresolved = {"pending_review", "reopened", "evidence_invalidated"}
    items = [
        item
        for item in items
        if item["review_priority"] == RiskLevel.HIGH.value
        and item["review_status"] in unresolved
    ]
    return _paginate(items, page=page, page_size=page_size)


@router.get("/applicability-queue", response_model=AssessmentListResponse)
def applicability_queue(
    report_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> dict:
    repo = Repository(session)
    if repo.get_report(report_id) is None:
        raise HTTPException(status_code=404, detail="report not found")
    _, assessments, risks, snapshots, _ = _report_assessments(repo, report_id)
    items = [
        _item(item, risks.get(item.assessment_id), snapshots.get(item.assessment_id))
        for item in assessments
    ]
    items = [
        item
        for item in items
        if item["applicability_status"] == ApplicabilityStatus.UNDETERMINED.value
    ]
    return _paginate(items, page=page, page_size=page_size)


@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailResponse)
def assessment_detail(report_id: str, assessment_id: str, session: Session = Depends(get_db_session)) -> dict:
    repo = Repository(session)
    assessment = repo.get_assessment(assessment_id)
    if assessment is None or assessment.report_id != report_id:
        raise HTTPException(status_code=404, detail="assessment not found")
    risk = repo.latest_risks_for_assessments([assessment_id]).get(assessment_id)
    snapshot = repo.latest_review_snapshot(assessment_id)
    task = repo.get_disclosure_task(assessment.run_id, assessment.requirement_id)
    ai_suggestion = repo.get_latest_ai_suggestion(assessment_id)
    evidence_items = []
    for evidence in assessment.evidence:
        pdf_page = evidence.source_pdf_page or evidence.source_page
        report_page = evidence.source_report_page
        page_label = f"PDF 第 {pdf_page} 页"
        if report_page is not None:
            page_label += f" / 报告页 {report_page}"
        evidence_items.append(
            {
                "evidence_id": evidence.evidence_id,
                "source_pdf_page": pdf_page,
                "source_report_page": report_page,
                "page_label": page_label,
                "evidence_preview": evidence.evidence_preview or evidence.source_text[:300],
                "source_method": evidence.source_method.value,
                "quality_flags": [flag.value for flag in evidence.quality_flags],
                "bbox": evidence.bbox,
            }
        )
    rationale = snapshot.rationale if snapshot and snapshot.rationale else assessment.rationale
    missing_items = (
        snapshot.missing_items
        if snapshot and snapshot.missing_items is not None
        else assessment.missing_items
    )
    human_rationale = bool(
        snapshot
        and snapshot.rationale is not None
        and snapshot.rationale != assessment.rationale
    )
    review_priority = risk.risk_level.value if risk else RiskLevel.HIGH.value
    return {
        "assessment_id": assessment.assessment_id,
        "requirement_id": assessment.requirement_id,
        "requirement_text": task.requirement_text if task else assessment.requirement_id,
        "source_requirement_text": (
            task.source_requirement_text if task and task.source_requirement_text else assessment.requirement_id
        ),
        "effective_requirement_text": task.requirement_text if task else assessment.requirement_id,
        "context_requirement_ids": task.context_requirement_ids if task else [],
        "structure_status": task.structure_status if task else "legacy_unavailable",
        "system_verdict": assessment.verdict.value,
        "system_rationale": assessment.rationale,
        "system_rationale_display": localize_rationale(assessment.rationale),
        "system_missing_items": assessment.missing_items,
        "system_missing_items_display": localize_missing_items(
            assessment.missing_items
        ),
        "reviewed_verdict": snapshot.reviewed_verdict.value if snapshot and snapshot.reviewed_verdict else None,
        "effective_verdict": snapshot.reviewed_verdict.value if snapshot and snapshot.reviewed_verdict else assessment.verdict.value,
        "review_status": _review_status(snapshot),
        "risk_level": review_priority,
        "review_priority": review_priority,
        "evidence_status": risk.evidence_status.value if risk and risk.evidence_status else None,
        "applicability_status": (
            risk.applicability_status.value if risk and risk.applicability_status else None
        ),
        "risk_reason_codes": risk.reason_codes if risk else ["risk_not_calculated"],
        "rationale": rationale,
        "rationale_display": localize_rationale(
            rationale,
            exact_only=human_rationale,
        ),
        "missing_items": missing_items,
        "missing_items_display": localize_missing_items(missing_items),
        "evidence_items": evidence_items,
        "latest_snapshot_id": snapshot.snapshot_id if snapshot else None,
        "latest_ai_suggestion": (
            ai_suggestion.model_dump(mode="json") if ai_suggestion else None
        ),
    }
