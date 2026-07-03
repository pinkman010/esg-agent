from src.domain.models import DisclosureAssessment, DisclosureTask, EvidenceItem
from src.tools.guardrails import build_guarded_assessment


def rule_based_judgment(task: DisclosureTask, evidence: list[EvidenceItem]) -> DisclosureAssessment:
    return build_guarded_assessment(task, evidence=evidence, model_called=False)