from pathlib import Path

from openpyxl import Workbook

from src.domain.ai_models import AIAssessmentSuggestion
from src.domain.enums import AISuggestionStatus, AssessmentVerdict, RiskLevel
from src.services.ai_evaluation_service import (
    AIEvaluationCase,
    ManualReviewRecord,
    evaluate_ai_suggestions,
    load_adjudication_pending_ids,
    load_manual_review_baseline,
)
from src.services.ai_assessment_service import AIAssessmentService
from tests.services.test_ai_assessment_service import FakeLLMClient, _candidate


def _write_review_workbook(path: Path, *, count: int = 225) -> None:
    workbook = Workbook()
    notes = workbook.active
    notes.title = "instructions"
    notes.append(["report_id", "report-1"])
    notes.append(["run_id", "run-1"])
    review = workbook.create_sheet("manual-review")
    review.append(
        [
            "requirement_id",
            "standard_verified",
            "manual_applicability",
            "suggested_verdict",
            "evidence_validity",
            "correct_pdf_pages",
            "rationale_correct",
            "missing_items_correct",
            "review_complete",
        ]
    )
    for index in range(1, count):
        review.append(
            [
                f"GRI 2-1-{index}",
                "yes",
                "applicable",
                "disclosed",
                "valid",
                "[41]",
                "yes",
                "yes",
                "complete",
            ]
        )
    review.append(
        [
            "GRI 2-30-b",
            "yes",
            "not_applicable_confirmed",
            None,
            "invalid",
            "[66]",
            "no",
            "no",
            "incomplete",
        ]
    )
    workbook.save(path)


def test_manual_review_loader_selects_224_complete_rows_plus_v1_exception(tmp_path):
    path = tmp_path / "manual.xlsx"
    _write_review_workbook(path)

    baseline = load_manual_review_baseline(path, expected_count=225)

    assert baseline.report_id == "report-1"
    assert baseline.run_id == "run-1"
    assert len(baseline.records) == 225
    exception = next(item for item in baseline.records if item.requirement_id == "GRI 2-30-b")
    assert exception.suggested_verdict is None
    assert exception.is_applicability_exception is True


def test_adjudication_recommendations_loader_reads_unique_requirement_ids(tmp_path):
    path = tmp_path / "recommendations.csv"
    path.write_text(
        "requirement_id,Pro_reason\nGRI 2-17-a,reason\nGRI 403-9-e,reason\n",
        encoding="utf-8",
    )

    assert load_adjudication_pending_ids(path) == {"GRI 2-17-a", "GRI 403-9-e"}


def _manual(
    requirement_id: str,
    verdict: AssessmentVerdict | None,
    pages: list[int],
) -> ManualReviewRecord:
    return ManualReviewRecord(
        requirement_id=requirement_id,
        standard_verified="yes",
        manual_applicability=(
            "not_applicable_confirmed" if verdict is None else "applicable"
        ),
        suggested_verdict=verdict,
        evidence_validity="valid",
        correct_pdf_pages=pages,
        rationale_correct="yes",
        missing_items_correct="yes",
        review_complete="complete" if verdict else "incomplete",
        is_applicability_exception=verdict is None,
    )


def _suggestion(
    assessment_id: str,
    *,
    status: AISuggestionStatus = AISuggestionStatus.SUCCEEDED,
    verdict: AssessmentVerdict | None = AssessmentVerdict.DISCLOSED,
    pages: list[int] | None = None,
    codes: list[str] | None = None,
    error_code: str | None = None,
) -> AIAssessmentSuggestion:
    return AIAssessmentSuggestion(
        suggestion_id=f"suggestion-{assessment_id}",
        assessment_id=assessment_id,
        run_id="run-1",
        status=status,
        provider="deepseek",
        model="deepseek-v4-flash",
        prompt_version="deepseek-gri-assist-v1",
        input_hash="a" * 64,
        suggested_verdict=verdict,
        evidence_ids=["evidence-1"] if pages else [],
        evidence_pdf_pages=pages or [],
        guardrail_codes=codes or [],
        error_code=error_code,
    )


def test_evaluation_metrics_count_failures_pages_false_disclosed_and_cross_distribution():
    cases = [
        AIEvaluationCase(
            manual=_manual("GRI 2-1-a", AssessmentVerdict.DISCLOSED, [41]),
            candidate=_candidate("GRI 2-1-a", review_priority=RiskLevel.LOW),
        ),
        AIEvaluationCase(
            manual=_manual("GRI 2-1-b", AssessmentVerdict.UNKNOWN, []),
            candidate=_candidate("GRI 2-1-b", review_priority=RiskLevel.MEDIUM),
        ),
        AIEvaluationCase(
            manual=_manual("GRI 2-1-c", AssessmentVerdict.PARTIALLY_DISCLOSED, [41]),
            candidate=_candidate("GRI 2-1-c", review_priority=RiskLevel.HIGH),
        ),
        AIEvaluationCase(
            manual=_manual("GRI 2-30-b", None, [66]),
            candidate=_candidate("GRI 2-30-b", review_priority=RiskLevel.MEDIUM),
        ),
    ]
    suggestions = [
        _suggestion("assessment-GRI 2-1-a", pages=[41]),
        _suggestion("assessment-GRI 2-1-b", pages=[41]),
        _suggestion(
            "assessment-GRI 2-1-c",
            status=AISuggestionStatus.FAILED,
            verdict=None,
            codes=["response_schema_invalid"],
            error_code="ai_response_validation_failed",
        ),
        _suggestion(
            "assessment-GRI 2-30-b",
            status=AISuggestionStatus.FAILED,
            verdict=None,
            codes=["evidence_reference_out_of_scope"],
            error_code="ai_response_guardrail_failed",
        ),
    ]

    result = evaluate_ai_suggestions(
        cases,
        suggestions,
        adjudication_pending_ids={"GRI 2-1-a"},
    )

    assert result.summary["evaluated_count"] == 4
    assert result.summary["verdict_evaluable_count"] == 3
    assert result.summary["exact_verdict_agreement_count"] == 1
    assert result.summary["wrong_source_page_count"] == 0
    assert result.summary["manual_evidence_page_disagreement_count"] == 1
    assert result.summary["all_rows_false_disclosed_count"] == 1
    assert result.summary["false_disclosed_count"] == 1
    assert result.summary["adjudication_pending_count"] == 1
    assert result.summary["unsupported_evidence_reference_count"] == 1
    assert result.summary["schema_failure_count"] == 1
    assert result.summary["model_failure_count"] == 0
    assert result.summary["rules_ai_disagreement_count"] == 2
    assert result.summary["manual_verdict_by_review_priority"]["disclosed|low"] == 1
    assert result.summary["manual_verdict_by_review_priority"]["unknown|medium"] == 1
    assert result.rows[0]["is_adjudication_pending"] is True


def test_pending_adjudication_is_reported_but_excluded_from_gold_dependent_gates():
    false_case = AIEvaluationCase(
        manual=_manual("GRI 2-17-a", AssessmentVerdict.UNKNOWN, []),
        candidate=_candidate("GRI 2-17-a", review_priority=RiskLevel.MEDIUM),
    )
    wrong_page_case = AIEvaluationCase(
        manual=_manual("GRI 403-9-e", AssessmentVerdict.DISCLOSED, [42]),
        candidate=_candidate("GRI 403-9-e", review_priority=RiskLevel.LOW),
    )
    suggestions = [
        _suggestion("assessment-GRI 2-17-a", pages=[41]),
        _suggestion("assessment-GRI 403-9-e", pages=[41]),
    ]

    result = evaluate_ai_suggestions(
        [false_case, wrong_page_case],
        suggestions,
        adjudication_pending_ids={"GRI 2-17-a", "GRI 403-9-e"},
    )

    assert result.summary["all_rows_false_disclosed_count"] == 1
    assert result.summary["all_rows_wrong_source_page_count"] == 1
    assert result.summary["false_disclosed_count"] == 0
    assert result.summary["wrong_source_page_count"] == 0


def test_unknown_citation_is_not_counted_as_wrong_disclosure_source_page():
    case = AIEvaluationCase(
        manual=_manual("GRI 2-1-a", AssessmentVerdict.UNKNOWN, []),
        candidate=_candidate("GRI 2-1-a", review_priority=RiskLevel.MEDIUM),
    )
    suggestion = _suggestion(
        "assessment-GRI 2-1-a",
        verdict=AssessmentVerdict.UNKNOWN,
        pages=[41],
    )

    result = evaluate_ai_suggestions([case], [suggestion])

    assert result.summary["wrong_source_page_count"] == 0
    assert result.summary["manual_evidence_page_disagreement_count"] == 0
    assert result.rows[0]["wrong_source_page"] is False


def test_fake_225_evaluation_completes_with_exact_metrics():
    cases = []
    for index in range(225):
        requirement_id = f"GRI 2-1-{index}"
        candidate = _candidate(
            requirement_id,
            review_priority=RiskLevel.LOW,
            verdict=AssessmentVerdict.DISCLOSED,
        )
        cases.append(
            AIEvaluationCase(
                manual=_manual(requirement_id, AssessmentVerdict.DISCLOSED, [41]),
                candidate=candidate,
            )
        )
    client = FakeLLMClient()
    service = AIAssessmentService(
        client,
        max_concurrency=8,
        max_calls_per_run=225,
    )

    suggestions = service.assess_explicit_candidates(
        [case.candidate for case in cases],
        confirm_llm=True,
    )

    result = evaluate_ai_suggestions(cases, suggestions)

    assert len(client.calls) == 225
    assert result.summary["evaluated_count"] == 225
    assert result.summary["exact_verdict_agreement_count"] == 225
    assert result.summary["exact_verdict_agreement_rate"] == 1.0
    assert result.summary["false_disclosed_count"] == 0
    assert result.summary["wrong_source_page_count"] == 0
