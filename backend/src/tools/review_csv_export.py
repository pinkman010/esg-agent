from __future__ import annotations

import json
from enum import Enum
from typing import Any


REVIEW_CSV_FIELDS = [
    "requirement_id",
    "verdict",
    "review_status",
    "rationale",
    "missing_items",
    "source_pdf_page",
    "source_report_page",
    "candidate_pdf_pages",
    "candidate_report_pages",
    "page_label",
    "retrieval_strategy",
    "candidate_page_source",
    "evidence_type",
    "quality_flags",
    "requires_ocr",
    "requires_vlm",
    "needs_ocr_or_vlm",
    "evidence_preview",
    "source_text",
]


def export_review_rows(assessments: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for assessment in assessments:
        evidence_items = _get(assessment, "evidence") or [{}]
        for evidence in _sort_evidence_items(evidence_items):
            rows.append(_row_from_assessment(assessment, evidence))
    return rows


def _sort_evidence_items(evidence_items: list[Any]) -> list[Any]:
    return sorted(evidence_items, key=_evidence_sort_key)


def _evidence_sort_key(evidence: Any) -> tuple[int, int]:
    source_pdf_page = _get(evidence, "source_pdf_page")
    candidate_pages = _candidate_pdf_pages(evidence)
    if source_pdf_page in candidate_pages:
        return (candidate_pages.index(source_pdf_page), int(source_pdf_page))
    if source_pdf_page is not None:
        return (len(candidate_pages), int(source_pdf_page))
    return (len(candidate_pages), 0)


def _row_from_assessment(assessment: Any, evidence: Any) -> dict[str, str]:
    row = {
        "requirement_id": _string(_get(assessment, "requirement_id")),
        "verdict": _string(_get(assessment, "verdict")),
        "review_status": _string(_get(assessment, "review_status")),
        "rationale": _string(_get(assessment, "rationale")),
        "missing_items": _json(_get(assessment, "missing_items", [])),
        "source_pdf_page": _string(_get(evidence, "source_pdf_page")),
        "source_report_page": _string(_get(evidence, "source_report_page")),
        "candidate_pdf_pages": _metadata_json(evidence, "candidate_pdf_pages"),
        "candidate_report_pages": _metadata_json(evidence, "candidate_report_pages"),
        "page_label": _page_label(evidence),
        "retrieval_strategy": _metadata_string(evidence, "retrieval_strategy"),
        "candidate_page_source": _metadata_string(evidence, "candidate_page_source"),
        "evidence_type": _evidence_type(evidence),
        "quality_flags": _json(_get(evidence, "quality_flags", [])),
        "requires_ocr": _bool_string(_get(evidence, "requires_ocr", False)),
        "requires_vlm": _bool_string(_get(evidence, "requires_vlm", False)),
        "needs_ocr_or_vlm": _bool_string(_get(evidence, "needs_ocr_or_vlm", False)),
        "evidence_preview": _string(_get(evidence, "evidence_preview")),
        "source_text": _string(_get(evidence, "source_text")),
    }
    return {field: row.get(field, "") for field in REVIEW_CSV_FIELDS}


def _metadata_json(evidence: Any, key: str) -> str:
    value = _get(evidence, key)
    if value is None:
        value = _get(_get(evidence, "metadata", {}), key, [])
    if key in {"candidate_pdf_pages", "candidate_report_pages"} and not value and not _has_real_evidence(evidence):
        return ""
    return _json(value or [])


def _has_real_evidence(evidence: Any) -> bool:
    return bool(_get(evidence, "source_pdf_page") or _get(evidence, "source_page") or _get(evidence, "source_text"))


def _candidate_pdf_pages(evidence: Any) -> list[int]:
    value = _get(evidence, "candidate_pdf_pages")
    if value is None:
        value = _get(_get(evidence, "metadata", {}), "candidate_pdf_pages", [])
    return [int(page) for page in value or [] if page is not None]


def _metadata_string(evidence: Any, key: str) -> str:
    value = _get(evidence, key)
    if value is None:
        value = _get(_get(evidence, "metadata", {}), key)
    return _string(value)


def _evidence_type(evidence: Any) -> str:
    evidence_type = _metadata_string(evidence, "evidence_type")
    if evidence_type:
        return evidence_type
    if _get(evidence, "source_pdf_page") or _get(evidence, "source_page"):
        return "substantive"
    return ""


def _page_label(evidence: Any) -> str:
    explicit = _get(evidence, "page_label")
    if explicit:
        return _string(explicit)
    metadata_label = _get(_get(evidence, "metadata", {}), "page_label")
    if metadata_label:
        return _string(metadata_label)
    source_pdf_page = _get(evidence, "source_pdf_page")
    source_report_page = _get(evidence, "source_report_page")
    if source_pdf_page and source_report_page:
        return f"PDF 第 {source_pdf_page} 页 / 报告页 {source_report_page}"
    if source_pdf_page:
        return f"PDF 第 {source_pdf_page} 页"
    return ""


def _json(value: Any) -> str:
    return json.dumps(_plain(value) or [], ensure_ascii=False)


def _string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _bool_string(value: Any) -> str:
    return "True" if bool(value) else "False"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value
