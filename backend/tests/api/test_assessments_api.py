from pathlib import Path

import pytest

from src.db.models import AssessmentRecord, AssessmentRiskRecord, ReviewSnapshotRecord
from src.db.repositories import Repository
from src.domain.ai_models import AIAssessmentSuggestion
from src.domain.enums import (
    AISuggestionStatus,
    ApplicabilityStatus,
    AssessmentVerdict,
    EvidenceSourceMethod,
    EvidenceStatus,
    ReportStatus,
    ReviewStatus,
    RiskLevel,
    RunStatus,
)
from src.domain.models import AnalysisRun, AssessmentRisk, DisclosureAssessment, DisclosureTask, EvidenceItem, Report
from src.api.routes.assessments import filter_scope_items
from src.services.risk_service import calculate_and_store_risk
from src.services.review_service import ReviewService
from src.standards.gri import GRIAdapter
from src.domain.enums import ReviewOperation

pytestmark = pytest.mark.anyio


def seed_assessments(session):
    repo = Repository(session)
    repo.create_report(
        Report(
            report_id="report-1",
            original_filename="report.pdf",
            stored_path="x",
            file_hash="hash-1",
            status=ReportStatus.ANALYSIS_COMPLETED,
        )
    )
    repo.create_run(AnalysisRun(run_id="run-1", report_id="report-1", status=RunStatus.COMPLETED))
    disclosed = DisclosureAssessment(
        assessment_id="assessment-low",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        verdict=AssessmentVerdict.DISCLOSED,
        rationale="Direct evidence.",
        evidence=[
            EvidenceItem(
                evidence_id="evidence-1",
                run_id="run-1",
                report_id="report-1",
                source_text="Legal name",
                source_page=1,
                source_file_hash="hash-1",
                source_method=EvidenceSourceMethod.PDFPLUMBER,
            )
        ],
        review_status=ReviewStatus.NOT_REQUIRED,
    )
    unknown = DisclosureAssessment(
        assessment_id="assessment-high",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-b",
        verdict=AssessmentVerdict.UNKNOWN,
        rationale="The report index contains an omission note, but no substantive disclosure evidence was found.",
        missing_items=[
            "EVG&D source basis from audited financial/P&L statement or internally audited management accounts",
            "applicability of EVG&D source basis",
        ],
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
    )
    for item in (disclosed, unknown):
        repo.save_assessment(item)
        for evidence in item.evidence:
            repo.save_evidence_item(item.assessment_id, evidence)
        calculate_and_store_risk(repo, item, trigger_event="analysis_completed")


async def test_dashboard_and_review_queue_use_latest_risk_records(api_client, api_session):
    seed_assessments(api_session)

    dashboard = await api_client.get("/api/reports/report-1/dashboard")
    queue = await api_client.get("/api/reports/report-1/review-queue")
    assessments = await api_client.get("/api/reports/report-1/assessments")

    assert dashboard.status_code == 200
    assert dashboard.json()["high_risk_total"] == 1
    assert dashboard.json()["high_risk_reviewed"] == 0
    assert queue.json()["total"] == 1
    assert queue.json()["items"][0]["requirement_id"] == "GRI 2-1-b"
    assert assessments.json()["total"] == 2
    assert {item["risk_level"] for item in assessments.json()["items"]} == {"high", "low"}

    ReviewService(Repository(api_session)).record(
        "assessment-high",
        operation_type=ReviewOperation.APPROVE,
        reviewer_name="张三",
        reason_code="system_result_confirmed",
    )
    reviewed_dashboard = await api_client.get("/api/reports/report-1/dashboard")
    reviewed_queue = await api_client.get("/api/reports/report-1/review-queue")
    assert reviewed_dashboard.json()["high_risk_reviewed"] == 1
    assert reviewed_queue.json()["total"] == 0

    Repository(api_session).update_run_status(
        "run-1",
        RunStatus.PARTIALLY_COMPLETED,
        eligible_requirement_count=3,
        succeeded_requirement_count=2,
        failed_requirement_count=1,
    )
    partial_dashboard = await api_client.get("/api/reports/report-1/dashboard")
    assert partial_dashboard.json()["risk_counts"] == {"low": 1, "high": 1}
    assert partial_dashboard.json()["review_priority_counts"] == {
        "low": 1,
        "high": 2,
    }
    assert partial_dashboard.json()["high_priority_total"] == 2
    assert partial_dashboard.json()["high_priority_unresolved"] == 1


async def test_assessment_detail_exposes_business_evidence_without_internal_route_metadata(api_client, api_session):
    seed_assessments(api_session)

    response = await api_client.get("/api/reports/report-1/assessments/assessment-low")

    assert response.status_code == 200
    body = response.json()
    assert body["assessment_id"] == "assessment-low"
    assert body["evidence_items"][0]["source_pdf_page"] == 1
    assert "metadata" not in body["evidence_items"][0]
    assert "candidate_pdf_pages" not in str(body)


async def test_assessment_detail_exposes_requirement_structure_and_latest_ai_suggestion(
    api_client,
    api_session,
):
    seed_assessments(api_session)
    repo = Repository(api_session)
    repo.save_disclosure_task(
        DisclosureTask(
            task_id="task-1",
            run_id="run-1",
            report_id="report-1",
            standard_id="GRI",
            standard_version="2021",
            disclosure_id="GRI 2-1",
            requirement_id="GRI 2-1-a",
            requirement_text="披露组织的法定名称。",
            source_requirement_text="法定名称",
            context_requirement_ids=["GRI 2-1"],
            structure_status="normalized",
        )
    )
    repo.append_ai_suggestion(
        AIAssessmentSuggestion(
            suggestion_id="ai-suggestion-1",
            assessment_id="assessment-low",
            run_id="run-1",
            status=AISuggestionStatus.SUCCEEDED,
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_version="deepseek-gri-assist-v1",
            input_hash="a" * 64,
            suggested_verdict=AssessmentVerdict.DISCLOSED,
            rationale_zh="报告直接披露了法定名称。",
            evidence_ids=["evidence-1"],
            evidence_pdf_pages=[1],
            confidence=0.91,
        )
    )

    response = await api_client.get(
        "/api/reports/report-1/assessments/assessment-low"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_requirement_text"] == "法定名称"
    assert body["effective_requirement_text"] == "披露组织的法定名称。"
    assert body["context_requirement_ids"] == ["GRI 2-1"]
    assert body["structure_status"] == "normalized"
    assert body["latest_ai_suggestion"]["suggested_verdict"] == "disclosed"
    assert body["system_verdict"] == "disclosed"


async def test_assessment_detail_keeps_audit_text_and_adds_chinese_display_fields(
    api_client,
    api_session,
):
    seed_assessments(api_session)

    response = await api_client.get(
        "/api/reports/report-1/assessments/assessment-high"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rationale"].startswith("The report index contains")
    assert body["rationale_display"] == "报告 GRI 内容索引包含从略说明，但未找到实质性披露证据。"
    assert body["missing_items"][0].startswith("EVG&D source basis")
    assert body["missing_items_display"] == [
        "EVG&D 数据来源依据：经审计的财务报表或损益表，或经内部审计的管理账目",
        "EVG&D 数据来源依据的适用性说明",
    ]


async def test_assessment_detail_keeps_rule_fields_separate_from_human_snapshot(
    api_client,
    api_session,
):
    seed_assessments(api_session)
    ReviewService(Repository(api_session)).record(
        "assessment-high",
        operation_type=ReviewOperation.MODIFY,
        reviewer_name="张三",
        reason_code="ai_suggestion_accepted",
        reviewer_note="人工采纳 AI 建议；AI suggestion_id=ai-suggestion-1",
        reviewed_verdict=AssessmentVerdict.UNKNOWN,
        rationale="AI 建议依据。",
        missing_items=[],
    )

    response = await api_client.get(
        "/api/reports/report-1/assessments/assessment-high"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["rationale"] == "AI 建议依据。"
    assert body["missing_items"] == []
    assert body["system_rationale"].startswith("The report index contains")
    assert body["system_rationale_display"] == (
        "报告 GRI 内容索引包含从略说明，但未找到实质性披露证据。"
    )
    assert body["system_missing_items"][0].startswith("EVG&D source basis")
    assert body["system_missing_items_display"] == [
        "EVG&D 数据来源依据：经审计的财务报表或损益表，或经内部审计的管理账目",
        "EVG&D 数据来源依据的适用性说明",
    ]


async def test_assessment_api_exposes_review_priority_alias_and_risk_v2_1_dimensions(
    api_client,
    api_session,
):
    seed_assessments(api_session)
    repo = Repository(api_session)
    repo.save_assessment_risk(
        AssessmentRisk(
            risk_id="risk-v2-1-api",
            assessment_id="assessment-high",
            risk_level=RiskLevel.LOW,
            reason_codes=["unknown_verdict", "no_valid_evidence"],
            risk_rule_version="risk-v2.1",
            trigger_event="risk_v2_1_enabled",
            evidence_status=EvidenceStatus.MISSING,
            applicability_status=ApplicabilityStatus.UNDETERMINED,
        )
    )

    listing = await api_client.get("/api/reports/report-1/assessments")
    detail = await api_client.get(
        "/api/reports/report-1/assessments/assessment-high"
    )

    assert listing.status_code == 200
    item = next(
        row for row in listing.json()["items"] if row["assessment_id"] == "assessment-high"
    )
    assert item["risk_level"] == item["review_priority"] == "low"
    assert item["evidence_status"] == "missing"
    assert item["applicability_status"] == "undetermined"
    assert detail.status_code == 200
    assert detail.json()["risk_level"] == detail.json()["review_priority"] == "low"
    assert detail.json()["evidence_status"] == "missing"
    assert detail.json()["applicability_status"] == "undetermined"


def seed_577_assessments(session):
    repo = Repository(session)
    repo.create_report(
        Report(
            report_id="report-577",
            original_filename="report.pdf",
            stored_path="x",
            file_hash="hash-577",
            status=ReportStatus.ANALYSIS_COMPLETED,
        )
    )
    repo.create_run(
        AnalysisRun(
            run_id="run-577",
            report_id="report-577",
            status=RunStatus.COMPLETED,
            risk_rule_version="risk-v2.1",
            eligible_requirement_count=577,
            succeeded_requirement_count=577,
        )
    )
    assessments = []
    risks = []
    for index in range(1, 578):
        assessment_id = f"assessment-{578 - index:03d}"
        assessments.append(
            AssessmentRecord(
                assessment_id=assessment_id,
                run_id="run-577",
                report_id="report-577",
                standard_id="GRI",
                standard_version="2021",
                disclosure_id=f"GRI 2-{index}",
                requirement_id=f"GRI 2-{index}-a",
                verdict="unknown",
                rationale="待核实",
                missing_items=[],
                model_called=False,
                review_status="needs_manual_review",
            )
        )
        risk_level = "high" if index <= 12 else "medium" if index <= 72 else "low"
        risks.append(
            AssessmentRiskRecord(
                risk_id=f"risk-{index:03d}",
                assessment_id=assessment_id,
                risk_level=risk_level,
                reason_codes=["test_distribution"],
                risk_rule_version="risk-v2.1",
                evidence_status="missing",
                applicability_status="undetermined" if index <= 343 else "applicable",
                trigger_event="analysis_completed",
            )
        )
    session.add_all(assessments)
    session.flush()
    session.add_all(risks)
    session.add_all(
        [
            ReviewSnapshotRecord(
                snapshot_id=f"snapshot-{index}",
                assessment_id=f"assessment-{578 - index:03d}",
                run_id="run-577",
                sequence=1,
                operation_type="approve",
                reviewer_name="张三",
                reason_code="system_result_confirmed",
                reviewer_note="",
                is_batch_operation=False,
            )
            for index in (1, 2)
        ]
    )
    session.commit()


async def test_assessments_pagination_reaches_all_577_in_stable_requirement_order(
    api_client,
    api_session,
):
    seed_577_assessments(api_session)

    responses = [
        await api_client.get(
            "/api/reports/report-577/assessments",
            params={"page": page, "page_size": 50},
        )
        for page in range(1, 14)
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["total"] == 577 for response in responses)
    assert [len(response.json()["items"]) for response in responses] == [
        *([50] * 11),
        27,
        0,
    ]
    requirement_ids = [
        item["requirement_id"]
        for response in responses
        for item in response.json()["items"]
    ]
    assert len(requirement_ids) == len(set(requirement_ids)) == 577
    assert requirement_ids[:3] == ["GRI 2-1-a", "GRI 2-2-a", "GRI 2-3-a"]
    assert requirement_ids[-1] == "GRI 2-577-a"


async def test_review_and_applicability_queues_filter_before_counting_and_pagination(
    api_client,
    api_session,
):
    seed_577_assessments(api_session)

    review_pages = [
        await api_client.get(
            "/api/reports/report-577/review-queue",
            params={"page": page, "page_size": 5},
        )
        for page in (1, 2, 3)
    ]
    applicability_pages = [
        await api_client.get(
            "/api/reports/report-577/applicability-queue",
            params={"page": page, "page_size": 50},
        )
        for page in range(1, 9)
    ]

    assert all(response.status_code == 200 for response in review_pages)
    assert [response.json()["total"] for response in review_pages] == [10, 10, 10]
    assert [len(response.json()["items"]) for response in review_pages] == [5, 5, 0]
    assert all(response.status_code == 200 for response in applicability_pages)
    assert all(response.json()["total"] == 343 for response in applicability_pages)
    assert [len(response.json()["items"]) for response in applicability_pages] == [
        *([50] * 6),
        43,
        0,
    ]


async def test_dashboard_separates_priority_and_applicability_counts(
    api_client,
    api_session,
):
    seed_577_assessments(api_session)

    response = await api_client.get("/api/reports/report-577/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["risk_counts"] == body["review_priority_counts"] == {
        "high": 12,
        "medium": 60,
        "low": 505,
    }
    assert body["high_risk_total"] == body["high_priority_total"] == 12
    assert body["high_risk_reviewed"] == body["high_priority_reviewed"] == 2
    assert body["high_priority_unresolved"] == 10
    assert body["applicability_counts"] == {
        "undetermined": 343,
        "applicable": 234,
    }
    assert body["applicability_undetermined_total"] == 343


def seed_v3_scope_assessments(session):
    repo = Repository(session)
    repo.create_report(
        Report(
            report_id="report-v3-scope",
            original_filename="report.pdf",
            stored_path="x",
            file_hash="hash-v3-scope",
            status=ReportStatus.ANALYSIS_COMPLETED,
        )
    )
    repo.create_run(
        AnalysisRun(
            run_id="run-v3-scope",
            report_id="report-v3-scope",
            status=RunStatus.COMPLETED,
            risk_rule_version="risk-v2.1",
            eligible_requirement_count=499,
            succeeded_requirement_count=499,
        )
    )
    backend_root = Path(__file__).resolve().parents[2]
    requirements = GRIAdapter(
        backend_root / "data/manifests/gri_requirement_checklist_v3.json"
    ).load_requirements()
    assessment_records = [
            AssessmentRecord(
                assessment_id=f"assessment-v3-{index:03d}",
                run_id="run-v3-scope",
                report_id="report-v3-scope",
                standard_id=requirement.standard_id,
                standard_version=requirement.standard_version,
                disclosure_id=requirement.disclosure_id,
                requirement_id=requirement.requirement_id,
                verdict="unknown",
                rationale="待核实",
                missing_items=[],
                model_called=False,
                review_status="needs_manual_review",
            )
            for index, requirement in enumerate(requirements, start=1)
    ]
    session.add_all(assessment_records)
    session.flush()
    session.add_all(
        [
            AssessmentRiskRecord(
                risk_id=f"risk-v3-{index:03d}",
                assessment_id=record.assessment_id,
                risk_level="high" if index <= 25 else "medium",
                reason_codes=["test_scope_filter"],
                risk_rule_version="risk-v2.1",
                evidence_status="missing",
                applicability_status=(
                    "undetermined" if index <= 30 else "applicable"
                ),
                trigger_event="analysis_completed",
            )
            for index, record in enumerate(assessment_records, start=1)
        ]
    )
    session.commit()


async def test_scope_items_exposes_complete_577_unit_range_without_fake_context_assessments(
    api_client,
    api_session,
):
    seed_v3_scope_assessments(api_session)

    first_page = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={"page": 1, "page_size": 100},
    )
    last_page = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={"page": 6, "page_size": 100},
    )
    dashboard = await api_client.get("/api/reports/report-v3-scope/dashboard")

    assert first_page.status_code == 200
    assert last_page.status_code == 200
    assert first_page.json()["total"] == last_page.json()["total"] == 577
    all_items = first_page.json()["items"] + last_page.json()["items"]
    assert any(item["unit_status"] == "assessed" for item in all_items)
    assert any(
        item["unit_status"] == "context_incorporated" for item in all_items
    )
    context = next(
        item
        for item in all_items
        if item["unit_status"] == "context_incorporated"
    )
    assert context["assessment_id"] is None
    assert context["effective_verdict"] is None
    assert context["review_priority"] is None
    assert context["review_status"] is None
    assert dashboard.status_code == 200
    assert dashboard.json()["standard_unit_count"] == 577


def seed_partial_retry_scope(session):
    repo = Repository(session)
    repo.create_report(
        Report(
            report_id="report-partial-retry",
            original_filename="partial.pdf",
            stored_path="x",
            file_hash="hash-partial-retry",
            status=ReportStatus.PARTIALLY_COMPLETED,
        )
    )
    backend_root = Path(__file__).resolve().parents[2]
    requirements = GRIAdapter(
        backend_root / "data/manifests/gri_requirement_checklist_v3.json"
    ).load_requirements()
    failed_requirement_id = requirements[-1].requirement_id
    repo.create_run(
        AnalysisRun(
            run_id="run-partial-parent",
            report_id="report-partial-retry",
            status=RunStatus.PARTIALLY_COMPLETED,
            eligible_requirement_count=499,
            succeeded_requirement_count=498,
            failed_requirement_count=1,
            failure_summary={
                "failed_requirement_ids": [failed_requirement_id],
            },
        )
    )
    session.add_all(
        [
            AssessmentRecord(
                assessment_id=f"assessment-partial-{index:03d}",
                run_id="run-partial-parent",
                report_id="report-partial-retry",
                standard_id=requirement.standard_id,
                standard_version=requirement.standard_version,
                disclosure_id=requirement.disclosure_id,
                requirement_id=requirement.requirement_id,
                verdict="unknown",
                rationale="待核实",
                missing_items=[],
                model_called=False,
                review_status="needs_manual_review",
            )
            for index, requirement in enumerate(requirements[:-1], start=1)
        ]
    )
    session.commit()
    repo.create_run(
        AnalysisRun(
            run_id="run-partial-retry",
            report_id="report-partial-retry",
            status=RunStatus.PARTIALLY_COMPLETED,
            parent_run_id="run-partial-parent",
            eligible_requirement_count=1,
            succeeded_requirement_count=0,
            failed_requirement_count=1,
            failure_summary={
                "retry_requirement_ids": [failed_requirement_id],
                "failed_requirement_ids": [failed_requirement_id],
            },
        )
    )
    return failed_requirement_id


async def test_partial_retry_exposes_complete_scope_and_parent_assessments(
    api_client,
    api_session,
):
    failed_requirement_id = seed_partial_retry_scope(api_session)

    scope = await api_client.get(
        "/api/reports/report-partial-retry/scope-items",
        params={"query": failed_requirement_id},
    )
    assessments = await api_client.get(
        "/api/reports/report-partial-retry/assessments",
        params={"page_size": 100},
    )
    review_queue = await api_client.get(
        "/api/reports/report-partial-retry/review-queue",
        params={"page_size": 100},
    )
    dashboard = await api_client.get(
        "/api/reports/report-partial-retry/dashboard"
    )

    assert scope.status_code == 200
    assert scope.json()["total"] == 1
    failed = scope.json()["items"][0]
    assert failed["requirement_id"] == failed_requirement_id
    assert failed["analysis_status"] == "failed"
    assert failed["source_run_id"] is None
    assert failed["failure_code"] == "assessment_failed"
    assert failed["assessment_id"] is None
    assert failed["effective_verdict"] is None
    assert assessments.status_code == 200
    assert assessments.json()["total"] == 498
    assert review_queue.status_code == 200
    assert review_queue.json()["total"] == 498
    assert dashboard.status_code == 200
    assert dashboard.json()["run_id"] == "run-partial-retry"
    assert dashboard.json()["verdict_counts"] == {"unknown": 498}
    assert dashboard.json()["failed_requirement_count"] == 1
    assert dashboard.json()["high_priority_total"] == 499


async def test_scope_items_searches_ids_and_text_before_pagination(
    api_client,
    api_session,
):
    seed_v3_scope_assessments(api_session)

    by_id = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={"query": "GRI 2-1", "page_size": 100},
    )
    by_english_text = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={"query": "LEGAL NAME"},
    )
    context_and_assessed = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={
            "query": "approach used for consolidating",
            "page_size": 100,
        },
    )
    no_match = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={"query": "不存在的核查文本"},
    )

    assert by_id.status_code == 200
    assert by_id.json()["total"] > 0
    assert all(
        "gri 2-1" in item["requirement_id"].casefold()
        for item in by_id.json()["items"]
    )
    assert by_english_text.json()["total"] == 1
    assert (
        by_english_text.json()["items"][0]["requirement_id"]
        == "GRI 2-1-a"
    )
    assert {
        item["unit_status"]
        for item in context_and_assessed.json()["items"]
    } == {"assessed", "context_incorporated"}
    assert no_match.json() == {
        "items": [],
        "page": 1,
        "page_size": 100,
        "total": 0,
    }


async def test_scope_items_combines_filters_then_paginates(
    api_client,
    api_session,
):
    seed_v3_scope_assessments(api_session)
    filters = {
        "effective_verdict": "unknown",
        "review_priority": "high",
        "review_status": "pending_review",
        "applicability_status": "undetermined",
        "page_size": 10,
    }

    first = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={**filters, "page": 1},
    )
    second = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={**filters, "page": 2},
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["total"] == second.json()["total"] == 25
    assert len(first.json()["items"]) == len(second.json()["items"]) == 10
    assert first.json()["items"] != second.json()["items"]
    for item in first.json()["items"] + second.json()["items"]:
        assert item["effective_verdict"] == "unknown"
        assert item["review_priority"] == "high"
        assert item["review_status"] == "pending_review"
        assert item["applicability_status"] == "undetermined"


async def test_scope_items_context_filter_preserves_context_semantics(
    api_client,
    api_session,
):
    seed_v3_scope_assessments(api_session)

    context = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={
            "unit_status": "context_incorporated",
            "page_size": 100,
        },
    )
    context_with_verdict = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params={
            "unit_status": "context_incorporated",
            "effective_verdict": "unknown",
        },
    )

    assert context.status_code == 200
    assert context.json()["total"] == 78
    assert all(
        item["effective_verdict"] is None
        and item["review_priority"] is None
        and item["review_status"] is None
        and item["applicability_status"] is None
        for item in context.json()["items"]
    )
    assert context_with_verdict.json()["total"] == 0
    assert context_with_verdict.json()["items"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"unit_status": "invalid"},
        {"effective_verdict": "invalid"},
        {"review_priority": "invalid"},
        {"review_status": "invalid"},
        {"applicability_status": "invalid"},
        {"query": "x" * 101},
    ],
)
async def test_scope_items_rejects_invalid_filters(
    api_client,
    api_session,
    params,
):
    seed_v3_scope_assessments(api_session)

    response = await api_client.get(
        "/api/reports/report-v3-scope/scope-items",
        params=params,
    )

    assert response.status_code == 422


def test_scope_filter_matches_chinese_effective_text():
    items = [
        {
            "requirement_id": "GRI 305-1-a",
            "gri_topic": "GRI 305",
            "unit_status": "assessed",
            "source_requirement_text": "Gross direct GHG emissions",
            "effective_requirement_text": "披露直接温室气体排放总量",
            "component_requirement_ids": [],
            "incorporated_into_requirement_ids": [],
            "effective_verdict": "unknown",
            "review_priority": "high",
            "review_status": "pending_review",
            "applicability_status": "undetermined",
        }
    ]

    result = filter_scope_items(
        items,
        query="温室气体",
        unit_status=None,
        effective_verdict=None,
        review_priority=None,
        review_status=None,
        applicability_status=None,
    )

    assert result == items
