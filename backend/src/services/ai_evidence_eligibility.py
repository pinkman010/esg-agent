from dataclasses import dataclass
from enum import StrEnum

from src.domain.enums import PageQualityFlag
from src.domain.models import EvidenceItem


NON_SUBSTANTIVE_EVIDENCE_TYPES = frozenset(
    {"omission_note", "index_statement", "chapter_cover", "candidate_page"}
)


class AIEvidenceCategory(StrEnum):
    SUBSTANTIVE = "substantive"
    EXPLICIT_NON_SUBSTANTIVE = "explicit_non_substantive"
    UNRESOLVED_IMAGE_BODY = "unresolved_image_body"


@dataclass(frozen=True)
class AIEvidenceEligibility:
    category: AIEvidenceCategory
    is_substantive: bool


def classify_ai_evidence(evidence: EvidenceItem) -> AIEvidenceEligibility:
    evidence_type = str(evidence.metadata.get("evidence_type") or "")
    if evidence_type in NON_SUBSTANTIVE_EVIDENCE_TYPES:
        return AIEvidenceEligibility(
            category=AIEvidenceCategory.EXPLICIT_NON_SUBSTANTIVE,
            is_substantive=False,
        )
    if PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED in evidence.quality_flags:
        return AIEvidenceEligibility(
            category=AIEvidenceCategory.UNRESOLVED_IMAGE_BODY,
            is_substantive=False,
        )
    return AIEvidenceEligibility(
        category=AIEvidenceCategory.SUBSTANTIVE,
        is_substantive=True,
    )
