import re

from src.domain.models import DisclosureRequirement, PageExtraction
from src.reports.profile import (
    AssurancePageProfile,
    IndexNotePageProfile,
    PageNumbering,
    ReportProfile,
    ReportKpiTableProfile,
    ReportRequirementRoute,
    ReportSectionProfile,
)


def calibrate_requirement_routes(
    profile: ReportProfile,
    reviewed_pages: dict[str, list[int]],
) -> ReportProfile:
    routes = dict(profile.requirement_routes)
    kpi_pages = set(profile.kpi_pdf_pages)
    for requirement_id, raw_pages in reviewed_pages.items():
        pages = sorted({page for page in raw_pages if 1 <= page <= profile.total_pdf_pages})
        existing = routes.get(requirement_id)
        metric_terms = list(existing.metric_terms) if existing is not None else []
        routes[requirement_id] = ReportRequirementRoute(
            candidate_pdf_pages=pages,
            kpi_table_pages=sorted(set(pages) & kpi_pages),
            metric_terms=metric_terms,
        )
    return profile.model_copy(update={"requirement_routes": routes})


def build_initial_profile(
    report_id: str,
    company_name: str,
    report_year: int,
    pdf_file: str,
    total_pdf_pages: int,
    pages: list[PageExtraction],
    report_index_pdf_page: int,
    report_index_report_page: int,
    requirements: list[DisclosureRequirement] | None = None,
) -> ReportProfile:
    index_pages = [page.page_number for page in pages if _looks_like_gri_index_page(page.text)]
    page_numbering = PageNumbering(
        report_index_pdf_page=report_index_pdf_page,
        report_index_report_page=report_index_report_page,
        total_pdf_pages=total_pdf_pages,
    )
    disclosure_routes = _extract_gri_index_routes(
        pages=pages,
        index_pdf_pages=index_pages,
        total_pdf_pages=total_pdf_pages,
        page_numbering=page_numbering,
    )
    kpi_tables = _kpi_tables(pages, page_numbering, report_year)
    kpi_pdf_pages = {page for table in kpi_tables for page in table.pdf_pages}
    return ReportProfile(
        report_id=report_id,
        company_name=company_name,
        report_year=report_year,
        pdf_file=pdf_file,
        total_pdf_pages=total_pdf_pages,
        page_numbering=page_numbering,
        gri_index={"pdf_pages": sorted(set(index_pages))},
        kpi_tables=kpi_tables,
        sections=_sections(pages, page_numbering, total_pdf_pages),
        index_note_pages=_index_note_pages(pages, page_numbering),
        assurance_pages=_assurance_pages(pages, page_numbering),
        requirement_routes=_requirement_routes(disclosure_routes, requirements or [], kpi_pdf_pages),
    )


def _index_note_pages(pages: list[PageExtraction], page_numbering: PageNumbering) -> list[IndexNotePageProfile]:
    note_pages: list[IndexNotePageProfile] = []
    for page in pages:
        note_types: list[str] = []
        if "从略披露" in page.text:
            note_types.append("omission_note")
        if "信息重述" in page.text or "未发生违法违规事件" in page.text:
            note_types.append("index_statement")
        if not note_types:
            continue
        note_pages.append(
            IndexNotePageProfile(
                pdf_page=page.page_number,
                report_page=page_numbering.report_page_for_pdf_page(page.page_number),
                note_types=note_types,
            )
        )
    return note_pages


def _looks_like_gri_index_page(text: str) -> bool:
    if "GRI" not in text:
        return False
    index_terms = (
        "披露项",
        "从略披露",
        "信息重述",
        "内容索引",
        "指标编号和描述",
        "GRI指标",
    )
    return any(term in text for term in index_terms)


def _extract_gri_index_routes(
    pages: list[PageExtraction],
    index_pdf_pages: list[int],
    total_pdf_pages: int,
    page_numbering: PageNumbering,
) -> dict[str, list[int]]:
    routes: dict[str, set[int]] = {}
    index_page_set = set(index_pdf_pages)
    two_up = page_numbering.is_two_up
    for page in pages:
        if page.page_number not in index_page_set:
            continue
        for disclosure_id, report_pages in _extract_disclosure_report_pages(page.text).items():
            pdf_pages = [
                _report_page_to_pdf_page(report_page, page_numbering, two_up=two_up)
                for report_page in report_pages
            ]
            valid_pages = [pdf_page for pdf_page in pdf_pages if 1 <= pdf_page <= total_pdf_pages]
            if valid_pages:
                routes.setdefault(disclosure_id, set()).update(valid_pages)
    return {disclosure_id: sorted(pdf_pages) for disclosure_id, pdf_pages in routes.items()}


def _extract_disclosure_report_pages(text: str) -> dict[str, list[int]]:
    normalized = " ".join(text.replace("，", ",").split())
    pattern = re.compile(
        r"(?<![\d-])(?P<disclosure>\d{1,3}-\d{1,3})(?!-[a-z0-9])"
        r"(?P<body>.{0,120}?)"
        r"(?P<pages>P\s*\d{1,3}(?:\s*[-—]\s*P?\s*\d{1,3})?(?:\s*,\s*P?\s*\d{1,3})*)",
        re.IGNORECASE,
    )
    routes: dict[str, list[int]] = {}
    for match in pattern.finditer(normalized):
        report_pages = _parse_report_page_token(match.group("pages"))
        if report_pages:
            routes[match.group("disclosure")] = report_pages
    return routes


def _parse_report_page_token(raw: str) -> list[int]:
    token = raw.upper().replace("P", "").replace(" ", "")
    pages: set[int] = set()
    for part in token.split(","):
        if not part:
            continue
        if "-" in part or "—" in part:
            start_text, end_text = re.split(r"[-—]", part, maxsplit=1)
            if start_text.isdigit() and end_text.isdigit():
                start = int(start_text)
                end = int(end_text)
                if start <= end:
                    pages.update(range(start, end + 1))
            continue
        if part.isdigit():
            pages.add(int(part))
    return sorted(pages)


def _report_page_to_pdf_page(report_page: int, page_numbering: PageNumbering, *, two_up: bool) -> int:
    if two_up:
        return page_numbering.pdf_page_for_report_page(report_page)
    return report_page + page_numbering.offset


def _requirement_routes(
    disclosure_routes: dict[str, list[int]],
    requirements: list[DisclosureRequirement],
    kpi_pdf_pages: set[int],
) -> dict[str, dict]:
    routes: dict[str, dict] = {}
    topic_routes = _topic_routes(disclosure_routes)
    for requirement in requirements:
        disclosure_id = requirement.disclosure_id.removeprefix("GRI ").strip()
        candidate_pages = disclosure_routes.get(disclosure_id) or _topic_candidate_pages(disclosure_id, topic_routes)
        if not candidate_pages:
            continue
        routes[requirement.requirement_id] = {
            "candidate_pdf_pages": candidate_pages,
            "kpi_table_pages": sorted(set(candidate_pages) & kpi_pdf_pages),
            "metric_terms": requirement.keywords,
        }
    return routes


def _kpi_tables(
    pages: list[PageExtraction],
    page_numbering: PageNumbering,
    report_year: int,
) -> list[ReportKpiTableProfile]:
    tables: list[ReportKpiTableProfile] = []
    year_pattern = re.compile(r"20\d{2}年?")
    for page in pages:
        normalized = " ".join(page.text.split())
        year_columns = sorted(set(year_pattern.findall(normalized)), reverse=True)
        has_metric_headers = "指标" in normalized and "单位" in normalized
        if not has_metric_headers or str(report_year) not in normalized:
            continue
        report_page = page_numbering.report_page_for_pdf_page(page.page_number)
        tables.append(
            ReportKpiTableProfile(
                name=f"KPI table PDF {page.page_number}",
                pdf_pages=[page.page_number],
                report_pages=[report_page] if report_page is not None else [],
                quality_flags=[flag.value for flag in page.quality_flags],
                year_columns=year_columns,
                known_metric_terms=[],
            )
        )
    return tables


def _topic_routes(disclosure_routes: dict[str, list[int]]) -> dict[str, list[int]]:
    routes: dict[str, set[int]] = {}
    for disclosure_id, pages in disclosure_routes.items():
        topic = _three_digit_topic(disclosure_id)
        if topic is None:
            continue
        routes.setdefault(topic, set()).update(pages)
    return {topic: sorted(pages) for topic, pages in routes.items()}


def _topic_candidate_pages(disclosure_id: str, topic_routes: dict[str, list[int]]) -> list[int] | None:
    topic = _three_digit_topic(disclosure_id)
    if topic is None:
        return None
    return topic_routes.get(topic)


def _three_digit_topic(disclosure_id: str) -> str | None:
    match = re.match(r"^(?P<topic>\d{3})-\d+", disclosure_id)
    if match is None:
        return None
    return match.group("topic")


def _sections(
    pages: list[PageExtraction],
    page_numbering: PageNumbering,
    total_pdf_pages: int,
) -> list[ReportSectionProfile]:
    section_terms = {
        "可持续发展管理": ["可持续发展管理", "利益相关方", "可持续发展战略", "实质性议题"],
        "产品服务与研发创新": ["产品服务与研发创新", "产品质量", "产品安全", "客户", "服务", "研发创新"],
        "诚信合规经营": ["诚信合规经营", "合规", "风险合规", "反腐败", "反竞争行为", "反垄断", "商业道德"],
        "绿色环保运营": ["绿色环保运营", "碳减排", "温室气体", "能源", "水资源", "废弃物", "生物多样性"],
        "可持续产业链": ["可持续产业链", "供应链", "供应商", "社会责任审核", "供应商筛选"],
        "公平健康工作环境": ["公平健康工作环境", "职业健康", "安全", "员工", "工伤", "职业病", "培训"],
        "和谐社区关系": ["和谐社区关系", "社区", "公益", "志愿者", "教育"],
    }
    section_order = {name: index for index, name in enumerate(section_terms)}
    starts: list[tuple[int, str]] = []
    previous_section: str | None = None
    previous_order = -1
    for page in pages:
        normalized = " ".join(page.text.split())
        section_name = _section_start_name(normalized, list(section_terms))
        if section_name is None or section_name == previous_section:
            continue
        section_index = section_order[section_name]
        if section_index <= previous_order:
            continue
        starts.append((page.page_number, section_name))
        previous_section = section_name
        previous_order = section_index

    if not starts:
        return []

    starts = sorted(starts)
    sections: list[ReportSectionProfile] = []
    for index, (start_page, section_name) in enumerate(starts):
        next_start = starts[index + 1][0] if index + 1 < len(starts) else min(total_pdf_pages + 1, start_page + 5)
        pdf_pages = list(range(start_page, max(start_page + 1, next_start)))
        sections.append(
            ReportSectionProfile(
                name=section_name,
                pdf_pages=pdf_pages,
                report_pages=[
                    report_page
                    for page in pdf_pages
                    if (report_page := _display_report_page_for_pdf_page(page, page_numbering)) is not None
                ],
                terms=section_terms[section_name],
            )
        )
    return sections


def _section_start_name(normalized_text: str, section_names: list[str]) -> str | None:
    heading_window = normalized_text[:220]
    hits = [section_name for section_name in section_names if section_name in heading_window]
    if len(hits) != 1:
        return None
    return hits[0]


def _display_report_page_for_pdf_page(pdf_page: int, page_numbering: PageNumbering) -> int | None:
    return page_numbering.report_page_for_pdf_page(pdf_page)


def _assurance_pages(pages: list[PageExtraction], page_numbering: PageNumbering) -> list[AssurancePageProfile]:
    assurance_pages: list[AssurancePageProfile] = []
    for page in pages:
        text = page.text
        if not any(term in text for term in ("审验声明", "鉴证报告", "第三方审验", "AA1000AS")):
            continue
        assurance_pages.append(
            AssurancePageProfile(
                pdf_page=page.page_number,
                report_page=page_numbering.report_page_for_pdf_page(page.page_number),
                requires_ocr=False,
                requires_vlm=False,
                quality_flags=[],
            )
        )
    return assurance_pages
