from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"


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
    SCANNED = "scanned"
    LOW_TEXT_DENSITY = "low_text_density"
    COMPLEX_TABLE = "complex_table"
    OCR_FAILED = "ocr_failed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"