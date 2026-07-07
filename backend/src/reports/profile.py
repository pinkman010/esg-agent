import json
from pathlib import Path

from pydantic import BaseModel, Field


class PageNumbering(BaseModel):
    report_index_pdf_page: int
    report_index_report_page: int
    total_pdf_pages: int | None = None

    @property
    def offset(self) -> int:
        return self.report_index_pdf_page - self.report_index_report_page

    @property
    def is_two_up(self) -> bool:
        return self.total_pdf_pages is not None and self.report_index_report_page > self.total_pdf_pages

    def report_page_for_pdf_page(self, pdf_page: int) -> int | None:
        if self.is_two_up:
            report_page = self.report_index_report_page + (pdf_page - self.report_index_pdf_page) * 2
        else:
            report_page = pdf_page - self.offset
        return report_page if report_page > 0 else None

    def pdf_page_for_report_page(self, report_page: int) -> int:
        if self.is_two_up:
            return self.report_index_pdf_page + (report_page - self.report_index_report_page) // 2
        return report_page + self.offset


class ReportKpiTableProfile(BaseModel):
    name: str
    pdf_pages: list[int]
    report_pages: list[int] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    year_columns: list[str] = Field(default_factory=list)
    known_metric_terms: list[str] = Field(default_factory=list)


class ReportSectionProfile(BaseModel):
    name: str
    pdf_pages: list[int]
    report_pages: list[int] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)


class AssurancePageProfile(BaseModel):
    pdf_page: int
    report_page: int | None = None
    requires_ocr: bool = False
    requires_vlm: bool = False
    quality_flags: list[str] = Field(default_factory=list)


class IndexNotePageProfile(BaseModel):
    pdf_page: int
    report_page: int | None = None
    note_types: list[str] = Field(default_factory=list)


class ReportRequirementRoute(BaseModel):
    candidate_pdf_pages: list[int] = Field(default_factory=list)
    kpi_table_pages: list[int] = Field(default_factory=list)
    metric_terms: list[str] = Field(default_factory=list)


class ReportProfile(BaseModel):
    report_id: str
    company_name: str
    report_year: int
    pdf_file: str
    total_pdf_pages: int
    page_numbering: PageNumbering
    gri_index: dict = Field(default_factory=dict)
    kpi_tables: list[ReportKpiTableProfile] = Field(default_factory=list)
    sections: list[ReportSectionProfile] = Field(default_factory=list)
    index_note_pages: list[IndexNotePageProfile] = Field(default_factory=list)
    assurance_pages: list[AssurancePageProfile] = Field(default_factory=list)
    requirement_routes: dict[str, ReportRequirementRoute] = Field(default_factory=dict)

    @property
    def kpi_pdf_pages(self) -> list[int]:
        return sorted({page for table in self.kpi_tables for page in table.pdf_pages})

    def report_page_for_pdf_page(self, pdf_page: int) -> int | None:
        return self.page_numbering.report_page_for_pdf_page(pdf_page)

    def pdf_page_for_report_page(self, report_page: int) -> int:
        return self.page_numbering.pdf_page_for_report_page(report_page)

    def is_kpi_page(self, pdf_page: int) -> bool:
        return pdf_page in set(self.kpi_pdf_pages)

    def route_for_requirement(self, requirement_id: str) -> ReportRequirementRoute | None:
        return self.requirement_routes.get(requirement_id)


def load_report_profile(path: Path) -> ReportProfile:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ReportProfile.model_validate(raw)
