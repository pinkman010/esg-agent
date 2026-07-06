from pathlib import Path

from src.domain.models import DisclosureTask
from src.reports.profile import load_report_profile
from src.tools.evidence_routing import EvidenceRouter


def make_task(requirement_id: str, disclosure_id: str | None = None) -> DisclosureTask:
    return DisclosureTask(
        task_id=f"task-{requirement_id}",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id=disclosure_id or requirement_id.rsplit("-", 1)[0],
        requirement_id=requirement_id,
        requirement_text="test requirement",
        keywords=["test"],
    )


def test_router_uses_report_profile_route_before_global_fallback():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 414-1-a", "GRI 414-1"))

    assert route.candidate_pdf_pages == [67]
    assert route.candidate_report_pages == [66]
    assert route.kpi_table_pages == [67]
    assert route.source == "report_profile"
    assert "profile:envision_2024" in route.reasons


def test_router_keeps_empty_route_for_explicit_no_evidence_candidate():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 305-2-c", "GRI 305-2"))

    assert route.candidate_pdf_pages == []
    assert route.candidate_report_pages == []
    assert route.source in {"contract", "empty"}


def test_router_merges_index_pages_when_profile_has_no_requirement_route():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    task = make_task("GRI 2-3-d", "GRI 2-3").model_copy(
        update={
            "candidate_pages": [3],
            "candidate_pdf_pages": [3],
            "candidate_report_pages": [2],
            "candidate_page_source": "gri_report_index",
        }
    )

    route = router.route(task)

    assert route.candidate_pdf_pages == [3]
    assert route.candidate_report_pages == [2]
    assert route.source == "gri_report_index"


def test_profile_takes_over_kpi_candidate_pages_after_contract_page_removal():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 308-1-a", "GRI 308-1"))

    assert route.candidate_pdf_pages == [67]
    assert route.source == "report_profile"


def test_profile_owns_migrated_environment_kpi_routes():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 303-4-b-i", "GRI 303-4"))

    assert route.candidate_pdf_pages == [63]
    assert route.candidate_report_pages == [62]
    assert route.kpi_table_pages == [63]
    assert route.source == "report_profile"
    assert "淡水排水量" in route.metric_terms


def test_profile_owns_migrated_social_kpi_routes():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 403-9-a-iii", "GRI 403-9"))

    assert route.candidate_pdf_pages == [67]
    assert route.candidate_report_pages == [66]
    assert route.kpi_table_pages == [67]
    assert route.source == "report_profile"
    assert "可记录工伤数量" in route.metric_terms


def test_profile_owns_migrated_section_routes():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 3-1-a", "GRI 3-1"))

    assert route.candidate_pdf_pages == [14, 15]
    assert route.candidate_report_pages == [13, 14]
    assert route.kpi_table_pages == []
    assert route.source == "report_profile"
    assert "利益相关方" in route.metric_terms


def test_profile_owns_migrated_index_note_routes():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 204-1-a", "GRI 204-1"))

    assert route.candidate_pdf_pages == [73]
    assert route.candidate_report_pages == [72]
    assert route.kpi_table_pages == []
    assert route.source == "report_profile"
    assert "从略披露" in route.metric_terms
