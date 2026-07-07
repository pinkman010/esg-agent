import re
from dataclasses import dataclass

from src.domain.models import DocumentChunk


@dataclass(frozen=True)
class KpiRowMatch:
    chunk: DocumentChunk
    row_label: str
    unit: str | None
    value: str | None
    year_column: str | None
    source_page: int
    preview: str


def match_kpi_rows(
    chunks: list[DocumentChunk],
    metric_terms: list[str],
    year_columns: list[str] | None = None,
) -> list[KpiRowMatch]:
    year_columns = year_columns or ["2024"]
    matches: list[KpiRowMatch] = []
    for chunk in chunks:
        normalized = " ".join(chunk.text.split())
        for term in metric_terms:
            term = term.strip()
            if not term or term not in normalized:
                continue
            match = _match_metric_line(normalized, term, year_columns)
            if match is None:
                continue
            unit, value, year = match
            matches.append(
                KpiRowMatch(
                    chunk=chunk,
                    row_label=term,
                    unit=unit,
                    value=value,
                    year_column=year,
                    source_page=chunk.source_page,
                    preview=_preview(normalized, term),
                )
            )
    return matches


def _match_metric_line(text: str, term: str, year_columns: list[str]) -> tuple[str | None, str | None, str | None] | None:
    index = text.find(term)
    if index < 0:
        return None
    window = text[index : index + 180]
    year = next((candidate for candidate in year_columns if candidate in text[:index] or candidate in window), None)
    after_term = window[len(term) :].strip()
    tokens = after_term.split()
    unit = tokens[0] if tokens else None
    value = None
    for token in tokens[1:]:
        if re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?%?", token):
            value = token
            break
    return unit, value, year


def _preview(text: str, term: str) -> str:
    index = text.find(term)
    if index < 0:
        return text[:140] + "..." if len(text) > 140 else text
    start = index
    end = min(len(text), index + len(term) + 120)
    preview = text[start:end].strip()
    if end < len(text):
        preview = f"{preview}..."
    return preview
