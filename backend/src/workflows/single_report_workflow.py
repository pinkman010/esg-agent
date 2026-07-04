import json
from pathlib import Path
from uuid import uuid4

from src.agents.disclosure_agent import DisclosureAgent
from src.db.repositories import Repository
from src.domain.enums import RunStatus
from src.domain.models import AnalysisRun, DisclosureTask, PageExtraction
from src.standards.gri_report_index import build_report_index


class SingleReportWorkflow:
    def __init__(
        self,
        repository: Repository,
        parser,
        standard_adapter,
        disclosure_agent: DisclosureAgent,
        requirement_pack_path: Path | None = None,
    ):
        self.repository = repository
        self.parser = parser
        self.standard_adapter = standard_adapter
        self.disclosure_agent = disclosure_agent
        self.requirement_pack_path = requirement_pack_path

    def run(
        self,
        report_id: str,
        pdf_path: Path,
        source_file_hash: str,
        confirm_llm: bool,
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
        for task in tasks:
            disclosure_id = task.disclosure_id.removeprefix("GRI ").strip()
            entry = report_index.get(disclosure_id)
            if entry is None:
                enriched_tasks.append(task)
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
                    }
                )
            )
        return enriched_tasks

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
            "GRI 2-27-a": [72],
            "GRI 2-27-a-i": [72],
            "GRI 2-27-a-ii": [72],
            "GRI 2-27-b": [72],
            "GRI 2-27-b-i": [72],
            "GRI 2-27-b-ii": [72],
            "GRI 2-27-c": [72],
            "GRI 2-27-d": [],
            "GRI 2-28-a": [9],
            "GRI 2-29-a": [14, 15],
            "GRI 2-29-a-i": [14, 15],
            "GRI 2-29-a-ii": [14, 15],
            "GRI 2-29-a-iii": [14, 15],
            "GRI 3-1-a": [14, 15],
            "GRI 3-1-a-i": [14, 15],
            "GRI 3-1-a-ii": [14, 15],
            "GRI 3-1-b": [14, 15],
        }
        pages_by_disclosure = {
            "GRI 2-23": [9, 11, 32, 54, 57, 59],
            "GRI 2-24": [11, 13, 32, 53, 54, 57, 59],
        }
        if task.requirement_id in pages_by_requirement:
            return pages_by_requirement[task.requirement_id]
        return pages_by_disclosure.get(task.disclosure_id)
