from dataclasses import dataclass

from src.domain.enums import AssessmentVerdict
from src.domain.models import DisclosureAssessment, DisclosureTask, DocumentChunk, Recommendation
from src.tools.guardrails import build_guarded_assessment
from src.tools.ids import database_safe_id
from src.tools.retrieval import retrieve_evidence


@dataclass(frozen=True)
class DisclosureAgentResult:
    assessment: DisclosureAssessment
    recommendations: list[Recommendation]


class DisclosureAgent:
    def analyze(
        self,
        task: DisclosureTask,
        chunks: list[DocumentChunk],
        confirm_llm: bool,
    ) -> DisclosureAgentResult:
        evidence = retrieve_evidence(task, chunks)
        assessment = build_guarded_assessment(task, evidence=evidence, model_called=False)
        recommendations = self._build_recommendations(task, assessment)
        return DisclosureAgentResult(assessment=assessment, recommendations=recommendations)

    def _build_recommendations(self, task: DisclosureTask, assessment: DisclosureAssessment) -> list[Recommendation]:
        if assessment.verdict is AssessmentVerdict.DISCLOSED:
            return []
        return [
            Recommendation(
                recommendation_id=database_safe_id(f"recommendation:{task.task_id}", "recommendation"),
                run_id=task.run_id,
                report_id=task.report_id,
                disclosure_id=task.disclosure_id,
                requirement_id=task.requirement_id,
                recommendation_text=f"Add report evidence for requirement {task.requirement_id}.",
            )
        ]
