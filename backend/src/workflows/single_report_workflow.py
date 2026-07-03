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
            enriched_tasks.append(
                task.model_copy(
                    update={
                        "candidate_pages": entry.candidate_pages,
                        "candidate_page_source": entry.source,
                        "index_page": entry.index_page,
                    }
                )
            )
        return enriched_tasks
