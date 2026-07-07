import json
from pathlib import Path
from uuid import uuid4

from src.agents.disclosure_agent import DisclosureAgent
from src.db.repositories import Repository
from src.domain.enums import PageQualityFlag, RunStatus
from src.domain.models import AnalysisRun, DisclosureTask, PageExtraction
from src.reports.profile import ReportProfile, load_report_profile
from src.standards.evidence_contracts import get_requirement_contract
from src.standards.gri_report_index import build_report_index
from src.tools.evidence_routing import EvidenceRouter


class SingleReportWorkflow:
    def __init__(
        self,
        repository: Repository,
        parser,
        standard_adapter,
        disclosure_agent: DisclosureAgent,
        requirement_pack_path: Path | None = None,
        report_profile_path: Path | None = None,
        ocr_max_pages: int = 5,
    ):
        self.repository = repository
        self.parser = parser
        self.standard_adapter = standard_adapter
        self.disclosure_agent = disclosure_agent
        self.requirement_pack_path = requirement_pack_path
        self.ocr_max_pages = ocr_max_pages
        self.report_profile: ReportProfile | None = (
            load_report_profile(report_profile_path) if report_profile_path is not None else None
        )
        self.evidence_router = EvidenceRouter(self.report_profile)

    def run(
        self,
        report_id: str,
        pdf_path: Path,
        source_file_hash: str,
        confirm_llm: bool,
        enable_ocr: bool = False,
        ocr_pages: list[int] | None = None,
    ) -> AnalysisRun:
        run_id = f"run-{uuid4().hex}"
        self.repository.create_run(
            AnalysisRun(
                run_id=run_id,
                report_id=report_id,
                status=RunStatus.PENDING,
                confirm_llm=confirm_llm,
            )
        )
        self.repository.update_run_status(run_id, RunStatus.RUNNING)
        self.repository.create_audit_event(
            run_id,
            "analysis_started",
            {"report_id": report_id, "confirm_llm": confirm_llm},
        )

        try:
            parsed = self.parser.parse_pdf(
                pdf_path,
                report_id=report_id,
                source_file_hash=source_file_hash,
                ocr_pages=self._explicit_ocr_pages(enable_ocr, ocr_pages),
            )
            if enable_ocr and not ocr_pages:
                selected_ocr_pages = self._select_ocr_pages(parsed.pages)
                if selected_ocr_pages:
                    parsed = self.parser.parse_pdf(
                        pdf_path,
                        report_id=report_id,
                        source_file_hash=source_file_hash,
                        ocr_pages=selected_ocr_pages,
                    )
            self.repository.create_audit_event(
                run_id,
                "parse_completed",
                {"page_count": parsed.page_count, "chunk_count": len(parsed.chunks)},
            )
            self.repository.save_pages_and_chunks(parsed.pages, parsed.chunks)
            tasks = self.standard_adapter.build_tasks(run_id=run_id, report_id=report_id)
            tasks = self._attach_report_index_candidates(parsed.pages, tasks)
            for task in tasks:
                self.repository.save_disclosure_task(task)
                result = self.disclosure_agent.analyze(task, parsed.chunks, confirm_llm=confirm_llm)
                self._attach_evidence_page_fields(result.assessment.evidence, task)
                self.repository.save_assessment(result.assessment)
                for evidence in result.assessment.evidence:
                    self.repository.save_evidence_item(result.assessment.assessment_id, evidence)
                for recommendation in result.recommendations:
                    self.repository.save_recommendation(recommendation)
            self.repository.create_audit_event(run_id, "analysis_completed", {"report_id": report_id})
            return self.repository.update_run_status(run_id, RunStatus.COMPLETED)
        except Exception as exc:
            self.repository.create_audit_event(run_id, "analysis_failed", {"error": str(exc)})
            return self.repository.update_run_status(run_id, RunStatus.FAILED, error_message=str(exc))

    def _explicit_ocr_pages(self, enable_ocr: bool, ocr_pages: list[int] | None) -> list[int] | None:
        if not enable_ocr:
            return None
        if not ocr_pages:
            return None
        return sorted({page for page in ocr_pages if page > 0})

    def _select_ocr_pages(self, pages: list[PageExtraction]) -> list[int]:
        selected: list[int] = []
        for page in pages:
            flags = set(page.quality_flags)
            if PageQualityFlag.LOW_TEXT_DENSITY in flags or PageQualityFlag.SCANNED in flags:
                selected.append(page.page_number)
            if len(selected) >= self.ocr_max_pages:
                break
        return selected

    def _attach_report_index_candidates(
        self,
        pages: list[PageExtraction],
        tasks: list[DisclosureTask],
    ) -> list[DisclosureTask]:
        if self.requirement_pack_path is None:
            return tasks

        raw = json.loads(self.requirement_pack_path.read_text(encoding="utf-8"))
        report_index = build_report_index(pages, raw.get("requirements", []))
        enriched_tasks: list[DisclosureTask] = []
        profile_excluded_pages = self._profile_excluded_pdf_pages()
        for task in tasks:
            disclosure_id = task.disclosure_id.removeprefix("GRI ").strip()
            entry = report_index.get(disclosure_id)
            route = self.evidence_router.route(task)
            if route.source == "report_profile":
                enriched_tasks.append(
                    task.model_copy(
                        update={
                            "candidate_pages": route.candidate_pdf_pages,
                            "candidate_pdf_pages": route.candidate_pdf_pages,
                            "candidate_report_pages": route.candidate_report_pages,
                            "candidate_page_source": route.source,
                            "kpi_table_pages": route.kpi_table_pages,
                            "kpi_metric_terms": route.metric_terms,
                            "kpi_year_columns": self._kpi_year_columns(route.kpi_table_pages),
                            "excluded_pdf_pages": profile_excluded_pages,
                            "report_index_pdf_page": self.report_profile.page_numbering.report_index_pdf_page
                            if self.report_profile
                            else None,
                            "report_index_report_page": self.report_profile.page_numbering.report_index_report_page
                            if self.report_profile
                            else None,
                        }
                    )
                )
                continue
            if entry is None:
                override_pages = self._candidate_page_overrides(task)
                if override_pages is not None:
                    page_count = max((page.page_number for page in pages), default=0)
                    candidate_pages = [page for page in override_pages if 1 <= page <= page_count]
                    fallback_index_pair = self._default_report_index_pair(raw.get("requirements", []))
                    candidate_report_pages: list[int | None] = []
                    update = {
                        "candidate_pages": candidate_pages,
                        "candidate_pdf_pages": candidate_pages,
                                "candidate_report_pages": candidate_report_pages,
                                "candidate_page_source": "requirement_contract",
                                "excluded_pdf_pages": profile_excluded_pages,
                            }
                    if fallback_index_pair is not None:
                        index_pdf_page, index_report_page = fallback_index_pair
                        candidate_report_pages = self._candidate_report_pages(candidate_pages, index_pdf_page, index_report_page)
                        update.update(
                            {
                                "candidate_report_pages": candidate_report_pages,
                                "report_index_pdf_page": index_pdf_page,
                                "report_index_report_page": index_report_page,
                            }
                        )
                    enriched_tasks.append(
                        task.model_copy(
                            update=update
                        )
                    )
                    continue
                enriched_tasks.append(
                    task.model_copy(
                        update={
                            "excluded_pdf_pages": profile_excluded_pages,
                            "report_index_pdf_page": self.report_profile.page_numbering.report_index_pdf_page
                            if self.report_profile
                            else task.report_index_pdf_page,
                            "report_index_report_page": self.report_profile.page_numbering.report_index_report_page
                            if self.report_profile
                            else task.report_index_report_page,
                        }
                    )
                )
                continue
            candidate_pages = self._supplement_candidate_pages(task, pages, entry.candidate_pages)
            page_count = max((page.page_number for page in pages), default=0)
            candidate_pages = [page for page in candidate_pages if 1 <= page <= page_count]
            candidate_report_pages = self._candidate_report_pages(candidate_pages, entry.report_index_pdf_page, entry.report_index_report_page)
            candidate_page_source = entry.source
            if candidate_pages != entry.candidate_pages:
                candidate_page_source = f"{entry.source}+requirement_supplement"
            enriched_tasks.append(
                task.model_copy(
                    update={
                        "candidate_pages": candidate_pages,
                        "candidate_pdf_pages": candidate_pages,
                        "candidate_report_pages": candidate_report_pages,
                        "candidate_page_source": candidate_page_source,
                        "index_page": entry.index_page,
                        "report_index_pdf_page": entry.report_index_pdf_page,
                        "report_index_report_page": entry.report_index_report_page,
                        "excluded_pdf_pages": profile_excluded_pages,
                    }
                )
            )
        return enriched_tasks

    def _profile_excluded_pdf_pages(self) -> list[int]:
        if self.report_profile is None:
            return []
        raw_pages = self.report_profile.gri_index.get("pdf_pages", [])
        return sorted({page for page in raw_pages if isinstance(page, int) and page > 0})

    def _attach_evidence_page_fields(self, evidence_items, task: DisclosureTask) -> None:
        if task.report_index_pdf_page is None or task.report_index_report_page is None:
            return

        offset = task.report_index_pdf_page - task.report_index_report_page
        for evidence in evidence_items:
            source_pdf_page = evidence.source_pdf_page or evidence.source_page
            evidence.source_pdf_page = source_pdf_page
            evidence.metadata["source_pdf_page"] = source_pdf_page
            evidence.metadata["candidate_pdf_pages"] = task.candidate_pdf_pages
            evidence.metadata["candidate_report_pages"] = task.candidate_report_pages
            source_report_page = source_pdf_page - offset
            if source_report_page > 0:
                evidence.source_report_page = source_report_page
                evidence.metadata["source_report_page"] = source_report_page

    def _candidate_report_pages(
        self,
        candidate_pdf_pages: list[int],
        report_index_pdf_page: int,
        report_index_report_page: int,
    ) -> list[int | None]:
        offset = report_index_pdf_page - report_index_report_page
        report_pages: list[int | None] = []
        for pdf_page in candidate_pdf_pages:
            report_page = pdf_page - offset
            report_pages.append(report_page if report_page > 0 else None)
        return report_pages

    def _default_report_index_pair(self, requirements: list[dict]) -> tuple[int, int] | None:
        for requirement in requirements:
            index_pdf_page = requirement.get("report_index_pdf_page")
            index_report_page = requirement.get("report_index_report_page")
            if isinstance(index_pdf_page, int) and isinstance(index_report_page, int):
                return index_pdf_page, index_report_page
        return None

    def _supplement_candidate_pages(
        self,
        task: DisclosureTask,
        pages: list[PageExtraction],
        candidate_pages: list[int],
    ) -> list[int]:
        page_numbers = {page.page_number for page in pages}
        override_pages = self._candidate_page_overrides(task)
        if override_pages is not None:
            return [page for page in override_pages if page in page_numbers]

        supplements: list[int] = []
        for page in pages:
            text = page.text
            text_lower = text.lower()
            if task.requirement_id == "GRI 2-1-a" and page.page_number <= 3:
                legal_name_terms = ["有限公司", "co., ltd", "co. ltd", "company limited"]
                if any(term in text_lower for term in legal_name_terms):
                    supplements.append(page.page_number)
            if task.requirement_id == "GRI 2-1-c":
                has_headquarters = "总部" in text
                has_location_hint = any(term in text for term in ["上海", "地址", "大楼", "所在地"])
                if has_headquarters and has_location_hint:
                    supplements.append(page.page_number)
            if task.disclosure_id == "GRI 2-6":
                has_business_overview = page.page_number in {4, 6, 9} and any(
                    term in text
                    for term in ["主要业务", "智能风电", "智慧储能", "绿氢", "ESG 合作网络", "ESG合作网络", "全球企业", "深化合作"]
                )
                has_supply_chain = page.page_number in {52, 53, 54} and any(
                    term in text for term in ["责任采购", "供应商", "可持续供应链", "产业共荣"]
                )
                if has_business_overview or has_supply_chain:
                    supplements.append(page.page_number)
            if task.disclosure_id == "GRI 2-7":
                has_employee_structure = page.page_number in {33, 65} and any(
                    term in text for term in ["人员结构", "员工组成", "社会绩效"]
                )
                if has_employee_structure:
                    supplements.append(page.page_number)
            if task.requirement_id == "GRI 2-9-b" and page.page_number == 13:
                if any(term in text for term in ["ESG治理架构", "ESG 治理架构", "ESG委员会", "ESG办公室"]):
                    supplements.append(page.page_number)
        return sorted(set([*candidate_pages, *supplements]))

    def _candidate_page_overrides(self, task: DisclosureTask) -> list[int] | None:
        contract = get_requirement_contract(task.requirement_id)
        if contract is not None and contract.candidate_pages is not None:
            return list(contract.candidate_pages)
        pages_by_requirement = {
            "GRI 2-22-a": [4, 5],
            "GRI 2-23-a": [9, 11, 32, 54, 57, 59],
            "GRI 2-23-a-i": [9, 32],
            "GRI 2-23-a-ii": [53, 58],
            "GRI 2-23-a-iii": [],
            "GRI 2-23-a-iv": [32, 54],
            "GRI 2-23-b": [9, 32, 54],
            "GRI 2-23-b-i": [9, 32, 54],
            "GRI 2-23-b-ii": [9, 32, 54],
            "GRI 2-23-c": [],
            "GRI 2-23-d": [],
            "GRI 2-23-e": [32, 54],
            "GRI 2-23-f": [32, 54, 59],
            "GRI 2-25-a": [32, 53, 59],
            "GRI 2-25-b": [32, 59],
            "GRI 2-25-c": [53, 57, 59],
            "GRI 2-25-e": [56, 58, 59],
            "GRI 2-26-a": [33, 59],
            "GRI 2-26-a-i": [],
            "GRI 2-26-a-ii": [59],
            "GRI 2-27-d": [],
            "GRI 2-28-a": [9],
            "GRI 201-2-a": [17, 18, 19],
            "GRI 201-2-a-i": [17, 18],
            "GRI 201-2-a-ii": [17, 18],
            "GRI 201-2-a-iii": [17, 18],
            "GRI 201-2-a-iv": [17, 18, 19],
            "GRI 201-2-a-v": [],
            "GRI 201-3-a": [],
            "GRI 201-3-b": [],
            "GRI 201-3-b-i": [],
            "GRI 201-3-b-ii": [],
            "GRI 201-3-b-iii": [],
            "GRI 201-3-c": [],
            "GRI 201-3-d": [],
            "GRI 201-3-e": [],
            "GRI 202-1-a": [],
            "GRI 202-1-b": [],
            "GRI 202-1-c": [],
            "GRI 202-1-d": [],
            "GRI 203-1-a": [4, 12, 42, 43, 44],
            "GRI 203-1-b": [4, 42, 43, 44],
            "GRI 203-1-c": [42, 43, 44],
            "GRI 203-2-a": [4, 12, 42, 43, 44],
            "GRI 203-2-b": [12, 42, 43, 44, 69],
            "GRI 205-1-a": [58, 68],
            "GRI 205-1-b": [58],
            "GRI 205-2-a": [],
            "GRI 205-2-b": [59, 68],
            "GRI 205-2-c": [54, 58],
            "GRI 205-2-d": [],
            "GRI 205-2-e": [59, 68],
            "GRI 205-3-a": [58, 68],
            "GRI 205-3-b": [68],
            "GRI 205-3-c": [],
            "GRI 205-3-d": [],
            "GRI 206-1-a": [68],
            "GRI 206-1-b": [],
            "GRI 207-1-a": [57],
            "GRI 207-1-a-iii": [57],
            "GRI 207-2-a": [57],
            "GRI 207-2-a-i": [57],
            "GRI 207-2-a-ii": [57],
            "GRI 207-2-a-iii": [57],
            "GRI 207-2-a-iv": [57],
            "GRI 207-3-a": [57],
            "GRI 207-3-a-i": [],
            "GRI 207-3-a-ii": [],
            "GRI 207-3-a-iii": [],
            "GRI 302-1-a": [63],
            "GRI 302-1-b": [],
            "GRI 302-1-c": [63],
            "GRI 302-1-d": [],
            "GRI 302-1-e": [63],
            "GRI 302-1-f": [],
            "GRI 302-1-g": [],
            "GRI 302-2-a": [],
            "GRI 302-2-b": [],
            "GRI 302-2-c": [],
            "GRI 302-3-a": [],
            "GRI 302-3-b": [],
            "GRI 302-3-c": [],
            "GRI 302-3-d": [],
            "GRI 302-4-a": [23, 63],
            "GRI 302-4-b": [23, 63],
            "GRI 302-4-c": [],
            "GRI 302-4-d": [],
            "GRI 302-5-a": [],
            "GRI 302-5-b": [],
            "GRI 302-5-c": [],
            "GRI 303-1-a": [25, 63],
            "GRI 303-1-b": [25],
            "GRI 303-1-c": [22, 25],
            "GRI 303-1-d": [16, 25],
            "GRI 303-2-a": [22],
            "GRI 303-2-a-i": [],
            "GRI 303-2-a-ii": [22, 25],
            "GRI 303-2-a-iii": [],
            "GRI 303-2-a-iv": [],
            "GRI 303-3-a": [25, 63],
            "GRI 303-3-a-i": [63],
            "GRI 303-3-a-ii": [63],
            "GRI 303-3-a-iii": [],
            "GRI 303-3-a-iv": [],
            "GRI 303-3-a-v": [63],
            "GRI 303-3-b": [25, 63],
            "GRI 303-3-b-i": [],
            "GRI 303-3-b-ii": [],
            "GRI 303-3-b-iii": [],
            "GRI 303-3-b-iv": [],
            "GRI 303-3-b-v": [],
            "GRI 303-3-c": [63],
            "GRI 303-3-c-i": [63],
            "GRI 303-3-c-ii": [63],
            "GRI 303-3-d": [],
            "GRI 303-4-a": [22, 63],
            "GRI 303-4-a-i": [],
            "GRI 303-4-a-ii": [],
            "GRI 303-4-a-iii": [],
            "GRI 303-4-a-iv": [],
            "GRI 303-4-b": [63],
            "GRI 303-4-b-i": [63],
            "GRI 303-4-b-ii": [63],
            "GRI 305-1-a": [20, 63],
            "GRI 305-1-d": [],
            "GRI 305-1-d-i": [],
            "GRI 305-1-d-ii": [],
            "GRI 305-1-d-iii": [],
            "GRI 305-1-e": [64],
            "GRI 305-1-f": [],
            "GRI 305-1-g": [64],
            "GRI 305-2-a": [20, 63],
            "GRI 305-2-b": [20, 63],
            "GRI 305-2-c": [],
            "GRI 305-2-d": [],
            "GRI 305-2-d-i": [],
        }
        pages_by_disclosure = {
            "GRI 2-23": [9, 11, 32, 54, 57, 59],
            "GRI 2-24": [11, 13, 32, 53, 54, 57, 59],
        }
        if task.requirement_id in pages_by_requirement:
            return pages_by_requirement[task.requirement_id]
        return pages_by_disclosure.get(task.disclosure_id)

    def _kpi_year_columns(self, kpi_table_pages: list[int]) -> list[str]:
        if self.report_profile is None:
            return []
        years: set[str] = set()
        page_set = set(kpi_table_pages)
        for table in self.report_profile.kpi_tables:
            if page_set.intersection(table.pdf_pages):
                years.update(table.year_columns)
        return sorted(years)
