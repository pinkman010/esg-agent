from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import AISuggestionStatus, AssessmentVerdict


class AIAssessmentSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_id: str
    assessment_id: str
    run_id: str
    status: AISuggestionStatus
    provider: str
    model: str
    prompt_version: str
    input_hash: str = Field(min_length=64, max_length=64)
    suggested_verdict: AssessmentVerdict | None = None
    rationale_zh: str | None = None
    missing_items_zh: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_pdf_pages: list[int] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    guardrail_codes: list[str] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
    finish_reason: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    raw_response: Any | None = None
    created_at: datetime | None = None

    @property
    def review_status(self) -> None:
        return None


class AIAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    suggested_verdict: Literal["disclosed", "partially_disclosed", "unknown"]
    evidence_ids: list[str]
    evidence_pdf_pages: list[int]
    rationale_zh: str = Field(min_length=1)
    missing_items_zh: list[str]
    confidence: float = Field(ge=0.0, le=1.0, strict=True)
