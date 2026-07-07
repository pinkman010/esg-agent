import re

from src.domain.models import DisclosureRequirement, PageExtraction
from src.reports.profile import AssurancePageProfile, IndexNotePageProfile, PageNumbering, ReportProfile


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
    )
    disclosure_routes = _extract_gri_index_routes(
        pages=pages,
        index_pdf_pages=index_pages,
        total_pdf_pages=total_pdf_pages,
        page_numbering=page_numbering,
    )
    return ReportProfile(
        report_id=report_id,
        company_name=company_name,
        report_year=report_year,
        pdf_file=pdf_file,
        total_pdf_pages=total_pdf_pages,
        page_numbering=page_numbering,
        gri_index={"pdf_pages": sorted(set(index_pages))},
        index_note_pages=_index_note_pages(pages, page_numbering),
        assurance_pages=_assurance_pages(pages, page_numbering),
        requirement_routes=_requirement_routes(disclosure_routes, requirements or []),
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
                report_page=page.page_number - page_numbering.offset,
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
    two_up = _looks_like_two_up_layout(page_numbering, total_pdf_pages)
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


def _looks_like_two_up_layout(page_numbering: PageNumbering, total_pdf_pages: int) -> bool:
    return page_numbering.report_index_report_page > total_pdf_pages


def _report_page_to_pdf_page(report_page: int, page_numbering: PageNumbering, *, two_up: bool) -> int:
    if two_up and report_page >= 2:
        return report_page // 2 + 2
    return report_page + page_numbering.offset


def _requirement_routes(
    disclosure_routes: dict[str, list[int]],
    requirements: list[DisclosureRequirement],
) -> dict[str, dict]:
    routes: dict[str, dict] = {}
    for requirement in requirements:
        disclosure_id = requirement.disclosure_id.removeprefix("GRI ").strip()
        candidate_pages = disclosure_routes.get(disclosure_id)
        if not candidate_pages:
            continue
        routes[requirement.requirement_id] = {
            "candidate_pdf_pages": candidate_pages,
            "kpi_table_pages": [],
            "metric_terms": requirement.keywords,
        }
    return routes


def _assurance_pages(pages: list[PageExtraction], page_numbering: PageNumbering) -> list[AssurancePageProfile]:
    assurance_pages: list[AssurancePageProfile] = []
    for page in pages:
        text = page.text
        if not any(term in text for term in ("审验声明", "鉴证报告", "第三方审验", "AA1000AS")):
            continue
        assurance_pages.append(
            AssurancePageProfile(
                pdf_page=page.page_number,
                report_page=page.page_number - page_numbering.offset,
                requires_ocr=False,
                requires_vlm=False,
                quality_flags=[],
            )
        )
    return assurance_pages
