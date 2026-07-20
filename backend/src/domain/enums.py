from enum import StrEnum


class ReportStatus(StrEnum):
    UPLOADED = "uploaded"
    METADATA_DETECTED = "metadata_detected"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    ANALYZING = "analyzing"
    ANALYSIS_COMPLETED = "analysis_completed"
    PARTIALLY_COMPLETED = "partially_completed"
    ANALYSIS_FAILED = "analysis_failed"
    HIGH_RISK_REVIEW_COMPLETED = "high_risk_review_completed"
    FORMALLY_EXPORTED = "formally_exported"
    REOPENED = "reopened"
    ARCHIVED = "archived"


class RiskLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceStatus(StrEnum):
    VALID_DIRECT = "valid_direct"
    MISSING = "missing"
    NON_SUBSTANTIVE_ONLY = "non_substantive_only"
    QUALITY_WARNING = "quality_warning"
    INVALID = "invalid"
    CONFLICT = "conflict"


class ApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE_CLAIMED = "not_applicable_claimed"
    NOT_APPLICABLE_CONFIRMED = "not_applicable_confirmed"
    UNDETERMINED = "undetermined"


class AISuggestionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"


class ReviewOperation(StrEnum):
    APPROVE = "approve"
    MODIFY = "modify"
    INVALIDATE_EVIDENCE = "invalidate_evidence"
    REOPEN = "reopen"
    LEGACY_IMPORT = "legacy_import"


class AssessmentVerdict(StrEnum):
    DISCLOSED = "disclosed"
    PARTIALLY_DISCLOSED = "partially_disclosed"
    NOT_DISCLOSED = "not_disclosed"
    UNKNOWN = "unknown"


class EvidenceSourceMethod(StrEnum):
    PYPDF = "pypdf"
    PDFPLUMBER = "pdfplumber"
    OCR = "ocr"
    DOCLING = "docling"
    VLM = "vlm"
    MANUAL = "manual"


class PageQualityFlag(StrEnum):
    DIGITAL_TEXT = "digital_text"
    SHORT_TEXT = "short_text"
    SCANNED = "scanned"
    LOW_TEXT_DENSITY = "low_text_density"
    COMPLEX_TABLE = "complex_table"
    IMAGE_BODY_NOT_EXTRACTED = "image_body_not_extracted"
    OCR_FAILED = "ocr_failed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
