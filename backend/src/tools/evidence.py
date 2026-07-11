import re

from src.domain.models import DisclosureTask, DocumentChunk, EvidenceItem
from src.tools.ids import database_safe_id


def evidence_id_for(task_id: str, chunk_id: str) -> str:
    raw_id = f"{task_id}:{chunk_id}"
    return database_safe_id(raw_id, "evidence")


def chunk_to_evidence(
    task: DisclosureTask,
    chunk: DocumentChunk,
    retrieval_metadata: dict | None = None,
) -> EvidenceItem:
    metadata = {**chunk.metadata, "task_id": task.task_id, "chunk_id": chunk.chunk_id}
    if retrieval_metadata:
        metadata.update(retrieval_metadata)
    metadata_preview = _metadata_preview(metadata)
    preview_keywords = [*task.keywords, *list(metadata.get("kpi_metric_terms") or [])]
    evidence_preview = metadata_preview or build_evidence_preview(chunk.text, preview_keywords)

    evidence_identity = str(metadata.get("evidence_identity") or "").strip()
    identity_chunk_id = f"{chunk.chunk_id}:{evidence_identity}" if evidence_identity else chunk.chunk_id

    return EvidenceItem(
        evidence_id=evidence_id_for(task.task_id, identity_chunk_id),
        run_id=task.run_id,
        report_id=task.report_id,
        source_text=chunk.text,
        source_page=chunk.source_page,
        source_file_hash=chunk.source_file_hash,
        source_method=chunk.source_method,
        bbox=chunk.bbox,
        quality_flags=chunk.quality_flags,
        evidence_preview=evidence_preview,
        metadata=metadata,
    )


def _metadata_preview(metadata: dict) -> str:
    for key in ("kpi_row_preview", "evidence_anchor_preview", "gri_index_row_preview", "section_heading_preview"):
        value = metadata.get(key)
        if value is None:
            continue
        preview = str(value).strip()
        if preview:
            return preview
    return ""


def build_evidence_preview(text: str, keywords: list[str], window_before: int = 80, window_after: int = 140) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""

    candidates = [
        _window_around_match(normalized, match_index, window_before, window_after)
        for match_index in _keyword_indexes(normalized, keywords)
    ]
    if not candidates:
        return normalized[:200] + "..." if len(normalized) > 200 else normalized

    return max(candidates, key=lambda candidate: _preview_score(candidate, keywords))


def build_kpi_evidence_preview(
    text: str,
    metric_terms: list[str],
    window_before: int = 20,
    window_after: int = 120,
) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""

    lower = normalized.lower()
    candidates: list[str] = []
    for term in metric_terms:
        term_lower = term.strip().lower()
        if not term_lower:
            continue
        start = 0
        while True:
            index = lower.find(term_lower, start)
            if index < 0:
                break
            window_start = max(0, index - window_before)
            window_end = min(len(normalized), index + len(term) + window_after)
            preview = normalized[window_start:window_end].strip()
            if window_start > 0 and window_before > 0:
                preview = f"...{preview}"
            if window_end < len(normalized):
                preview = f"{preview}..."
            candidates.append(preview)
            start = index + max(1, len(term_lower))

    if not candidates:
        return build_evidence_preview(normalized, metric_terms)

    return max(candidates, key=lambda candidate: (sum(char.isdigit() for char in candidate), len(candidate)))


def _nearest_disclosure_anchor_start(text: str, match_index: int) -> int | None:
    prefix = text[:match_index]
    matches = list(re.finditer(r"(?:^|\s)(\d{1,3}-\d{1,3}(?:-[a-z]+(?:-[ivx]+)?)?)\s", prefix))
    if not matches:
        return None
    return matches[-1].start(1)


def _next_disclosure_anchor_start(text: str, match_index: int) -> int | None:
    suffix = text[match_index:]
    match = re.search(r"\s\d{1,3}-\d{1,3}(?:-[a-z]+(?:-[ivx]+)?)?\s", suffix)
    if match is None:
        return None
    return match_index + match.start()


def _keyword_indexes(text: str, keywords: list[str]) -> list[int]:
    text_lower = text.lower()
    indexes: list[int] = []
    for keyword in keywords:
        keyword_lower = keyword.strip().lower()
        if not keyword_lower:
            continue
        start = 0
        while True:
            index = text_lower.find(keyword_lower, start)
            if index < 0:
                break
            indexes.append(index)
            start = index + max(1, len(keyword_lower))
    return sorted(set(indexes))


def _window_around_match(text: str, match_index: int, window_before: int, window_after: int) -> str:
    start = _nearest_disclosure_anchor_start(text, match_index)
    anchored = start is not None
    if start is None:
        start = max(0, match_index - window_before)
    end = min(len(text), match_index + window_after)
    ended_at_next_anchor = False
    if anchored:
        next_anchor = _next_disclosure_anchor_start(text, match_index)
        if next_anchor is not None:
            end = min(end, next_anchor)
            ended_at_next_anchor = True
    preview = text[start:end]
    if start > 0 and not anchored:
        preview = f"...{preview}"
    if end < len(text) and not ended_at_next_anchor:
        preview = f"{preview}..."
    return preview.strip()


def _preview_score(preview: str, keywords: list[str]) -> tuple[int, int, int, int, int]:
    preview_lower = preview.lower()
    keyword_hits = sum(1 for keyword in keywords if keyword.strip() and keyword.lower() in preview_lower)
    keyword_specificity = sum(len(keyword.strip()) for keyword in keywords if keyword.strip() and keyword.lower() in preview_lower)
    has_email = 1 if re.search(r"[\w.+-]+@[\w.-]+", preview) else 0
    has_date = 1 if re.search(r"20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", preview) else 0
    has_numeric = 1 if re.search(r"\d", preview) else 0
    return (keyword_hits, keyword_specificity, has_email, has_date, has_numeric)
