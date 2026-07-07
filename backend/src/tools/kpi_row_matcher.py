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
    window = text[max(0, index - 80) : index + len(term) + 180]
    year = next((candidate for candidate in year_columns if candidate in text[:index] or candidate in window), None)
    after_term = text[index + len(term) : index + len(term) + 120].strip()
    before_term = text[max(0, index - 80) : index]
    tokens = after_term.split()
    unit = _infer_unit(after_term, tokens)
    value = _first_numeric_value(after_term, skip_first_token=unit is not None and bool(tokens))
    if value is None and not _has_no_data_before_numeric(after_term):
        value = _first_numeric_value(before_term)
    if value is None:
        return None
    return unit, value, year


def _first_numeric_value(text: str, *, skip_first_token: bool = False) -> str | None:
    if _has_no_data_before_numeric(text):
        return None
    tokens = text.split()
    if skip_first_token and len(tokens) > 1:
        for token in tokens[1:4]:
            if re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?%?", token):
                return token
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?%?", text)
    return match.group(0) if match else None


def _has_no_data_before_numeric(text: str) -> bool:
    marker_index = text.find("无数据")
    if marker_index < 0:
        return False
    numeric_match = re.search(r"-?\d[\d,]*(?:\.\d+)?%?", text)
    return numeric_match is not None and marker_index < numeric_match.start()


def _infer_unit(text: str, tokens: list[str]) -> str | None:
    if tokens and tokens[0] in {"%", "家", "人", "次", "小时", "天", "tCO2e", "吨", "MWh", "kWh"}:
        return tokens[0]
    for unit in ("%", "家", "人", "次", "小时", "天", "tCO2e", "吨", "MWh", "kWh"):
        if unit in text[:40]:
            return unit
    return None


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
