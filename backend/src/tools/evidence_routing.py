from dataclasses import dataclass, field

from src.domain.models import DisclosureTask
from src.reports.profile import ReportProfile
from src.standards.evidence_contracts import get_requirement_contract
from src.standards.evidence_ontology import RequirementFacet, SemanticGroup


TOPIC_SECTION_MAP = {
    "205": "诚信合规经营",
    "206": "诚信合规经营",
    "207": "诚信合规经营",
    "302": "绿色环保运营",
    "303": "绿色环保运营",
    "304": "绿色环保运营",
    "305": "绿色环保运营",
    "306": "绿色环保运营",
    "308": "可持续产业链",
    "401": "公平健康工作环境",
    "402": "公平健康工作环境",
    "403": "公平健康工作环境",
    "404": "公平健康工作环境",
    "405": "公平健康工作环境",
    "406": "公平健康工作环境",
    "407": "公平健康工作环境",
    "408": "公平健康工作环境",
    "409": "公平健康工作环境",
    "410": "公平健康工作环境",
    "413": "和谐社区关系",
    "414": "可持续产业链",
    "416": "产品服务与研发创新",
    "417": "产品服务与研发创新",
}


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
            metric_terms = self._metric_terms_with_semantic_aliases(
                list(profile_route.metric_terms),
                task,
                contract,
            )
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=self._report_pages(pages),
                kpi_table_pages=self._valid_pages(profile_route.kpi_table_pages),
                metric_terms=metric_terms,
                source="report_profile",
                reasons=[f"profile:{self.report_profile.report_id}"] if self.report_profile else [],
            )

        if contract is not None and contract.candidate_pages is not None:
            raw_pages = list(contract.candidate_pages)
            pages = self._valid_pages(raw_pages)
            if not raw_pages or pages:
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
        topic_section = self._topic_section_name(task)
        if topic_section:
            section = next((item for item in self.report_profile.sections if item.name == topic_section), None)
            if section is not None:
                pages = self._valid_pages(section.pdf_pages)
                if pages:
                    return EvidenceRoute(
                        candidate_pdf_pages=pages,
                        candidate_report_pages=self._report_pages(pages),
                        kpi_table_pages=[],
                        metric_terms=list(section.terms),
                        source="report_profile_section",
                        reasons=[f"profile_section:{self.report_profile.report_id}:{section.name}:topic"],
                    )
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

    def _topic_section_name(self, task: DisclosureTask) -> str | None:
        disclosure_id = task.disclosure_id.removeprefix("GRI ").strip()
        topic = disclosure_id.split("-", 1)[0]
        return TOPIC_SECTION_MAP.get(topic)

    def _metric_terms_with_semantic_aliases(self, terms: list[str], task: DisclosureTask, contract) -> list[str]:
        aliases: list[str] = []
        if contract is not None and contract.semantic_group is SemanticGroup.ANTI_CORRUPTION_RISK:
            aliases.extend(["反腐败", "审计策略", "风险程度", "商业道德问题", "反舞弊"])
        if (
            contract is not None
            and contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
            and RequirementFacet.REQUIRES_NEW_SUPPLIER_SCOPE in contract.facets
        ):
            aliases.extend(["供应商社会责任审核", "社会责任审核率", "社会评价", "社会标准"])
        if (
            contract is not None
            and contract.semantic_group is SemanticGroup.OHS_KPI
            and RequirementFacet.REQUIRES_COUNT in contract.facets
            and "fatalit" in task.requirement_text.lower()
        ):
            aliases.extend(["员工因工死亡人数", "因工死亡人数", "工伤死亡人数"])
        if contract is not None and contract.semantic_group is SemanticGroup.BREAKDOWN_DIMENSION:
            if RequirementFacet.REQUIRES_GENDER_BREAKDOWN in contract.facets:
                aliases.extend(["按性别划分", "男性", "女性", "人均培训小时数"])
            if RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN in contract.facets:
                aliases.extend(["按层级划分", "高级管理层", "中基层管理", "基层员工", "人均培训小时数"])
        if contract is not None and contract.semantic_group is SemanticGroup.COMMUNITY_PROGRAM:
            aliases.extend(["环境影响评价", "环境影响评估", "环境监测", "环境风险评估"])
        return _dedupe_terms([*terms, *aliases])


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for term in terms:
        normalized = term.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
