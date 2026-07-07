from dataclasses import dataclass, field

from src.domain.models import DisclosureTask
from src.reports.profile import ReportProfile
from src.standards.evidence_contracts import get_requirement_contract


@dataclass(frozen=True)
class EvidenceRoute:
    candidate_pdf_pages: list[int] = field(default_factory=list)
    candidate_report_pages: list[int | None] = field(default_factory=list)
    kpi_table_pages: list[int] = field(default_factory=list)
    metric_terms: list[str] = field(default_factory=list)
    source: str = "empty"
    reasons: list[str] = field(default_factory=list)


class EvidenceRouter:
    def __init__(self, report_profile: ReportProfile | None = None):
        self.report_profile = report_profile

    def route(self, task: DisclosureTask) -> EvidenceRoute:
        contract = get_requirement_contract(task.requirement_id)
        profile_route = self.report_profile.route_for_requirement(task.requirement_id) if self.report_profile else None

        if profile_route is not None:
            pages = self._valid_pages(profile_route.candidate_pdf_pages)
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=self._report_pages(pages),
                kpi_table_pages=self._valid_pages(profile_route.kpi_table_pages),
                metric_terms=list(profile_route.metric_terms),
                source="report_profile",
                reasons=[f"profile:{self.report_profile.report_id}"] if self.report_profile else [],
            )

        if contract is not None and contract.candidate_pages is not None:
            pages = self._valid_pages(list(contract.candidate_pages))
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=self._report_pages(pages),
                kpi_table_pages=list(contract.kpi_table_pages or ()),
                source="contract",
                reasons=["contract:candidate_pages"],
            )

        if task.candidate_pdf_pages:
            pages = self._valid_pages(task.candidate_pdf_pages)
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=task.candidate_report_pages,
                source=task.candidate_page_source or "gri_report_index",
                reasons=[task.candidate_page_source or "gri_report_index"],
            )

        if task.candidate_pages:
            pages = self._valid_pages(task.candidate_pages)
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=self._report_pages(pages),
                source=task.candidate_page_source or "candidate_pages",
                reasons=[task.candidate_page_source or "candidate_pages"],
            )

        section_route = self._section_route(task)
        if section_route is not None:
            return section_route

        return EvidenceRoute()

    def _valid_pages(self, pages: list[int]) -> list[int]:
        if self.report_profile is None:
            return sorted({page for page in pages if page > 0})
        return sorted({page for page in pages if 1 <= page <= self.report_profile.total_pdf_pages})

    def _report_pages(self, pdf_pages: list[int]) -> list[int | None]:
        if self.report_profile is None:
            return []
        return [self.report_profile.report_page_for_pdf_page(page) for page in pdf_pages]

    def _section_route(self, task: DisclosureTask) -> EvidenceRoute | None:
        if self.report_profile is None:
            return None
        haystack = " ".join([task.requirement_text, *task.keywords]).lower()
        best_section = None
        best_score = 0
        for section in self.report_profile.sections:
            score = 0
            for term in section.terms:
                term_lower = term.lower()
                if term_lower and term_lower in haystack:
                    score += 1
            if score > best_score:
                best_score = score
                best_section = section
        if best_section is None or best_score == 0:
            return None
        pages = self._valid_pages(best_section.pdf_pages)
        if not pages:
            return None
        return EvidenceRoute(
            candidate_pdf_pages=pages,
            candidate_report_pages=self._report_pages(pages),
            kpi_table_pages=[],
            metric_terms=list(best_section.terms),
            source="report_profile_section",
            reasons=[f"profile_section:{self.report_profile.report_id}:{best_section.name}"],
        )
