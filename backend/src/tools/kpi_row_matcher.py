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
    matched_term: str
    scope_tokens: tuple[str, ...]
    value_type: str


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
            span = _find_term_span(normalized, term)
            if not term or span is None:
                continue
            match = _match_metric_line(normalized, span, year_columns)
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
                    preview=_preview(normalized, span),
                    matched_term=term,
                    scope_tokens=_scope_tokens(normalized, span),
                    value_type=_value_type(term, unit, value),
                )
            )
    return matches


def _match_metric_line(text: str, span: tuple[int, int], year_columns: list[str]) -> tuple[str | None, str | None, str | None] | None:
    index, term_end = span
    window = text[max(0, index - 80) : term_end + 180]
    year = next((candidate for candidate in year_columns if candidate in text[:index] or candidate in window), None)
    after_term = text[term_end : term_end + 120].strip()
    before_term = text[max(0, index - 80) : index]
    tokens = after_term.split()
    unit = _infer_unit(after_term, tokens)
    value = _first_numeric_value(after_term, skip_first_token=unit is not None and bool(tokens))
    if value is None:
        value = _first_numeric_value(text[index:term_end])
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


def _preview(text: str, span: tuple[int, int]) -> str:
    index, term_end = span
    start = index
    end = min(len(text), term_end + 120)
    preview = text[start:end].strip()
    if end < len(text):
        preview = f"{preview}..."
    return preview


def _scope_tokens(text: str, span: tuple[int, int]) -> tuple[str, ...]:
    index, term_end = span
    window = text[max(0, index - 40) : term_end + 80].lower()
    mappings = (
        ("scope_1", ("范围一", "scope 1", "scope1")),
        ("scope_2", ("范围二", "scope 2", "scope2")),
        ("scope_3", ("范围三", "scope 3", "scope3")),
        ("employee", ("员工", "employee")),
        ("external_worker", ("外部供方", "承包商", "contractor", "non-employee")),
        ("location_based", ("基于位置", "location-based")),
        ("market_based", ("基于市场", "market-based")),
        ("environmental", ("环境", "environmental")),
        ("social", ("社会", "social")),
    )
    return tuple(name for name, terms in mappings if any(value in window for value in terms))


def _find_term_span(text: str, term: str) -> tuple[int, int] | None:
    if not term:
        return None
    direct_index = text.find(term)
    if direct_index >= 0:
        return direct_index, direct_index + len(term)
    compact_term = re.sub(r"[\s/]+", "", term)
    if not compact_term:
        return None
    parts = [r"(?:或|/)" if char == "或" else re.escape(char) for char in compact_term]
    # Multi-column PDF extraction can inject year values in the middle of a row label.
    separator = r"[\s\d.,%/]*?"
    pattern = separator.join(parts)
    match = re.search(pattern, text)
    return (match.start(), match.end()) if match is not None else None


def _value_type(term: str, unit: str | None, value: str | None) -> str:
    haystack = f"{term} {unit or ''}".lower()
    if unit == "%" or (value and value.endswith("%")):
        return "percentage"
    if "tco2e" in haystack or "温室气体" in haystack or "碳排放" in haystack:
        return "emissions"
    if unit in {"kWh", "MWh"} or "能源" in term or "用电" in term:
        return "energy"
    if unit in {"人", "家", "次"}:
        return "count"
    if unit in {"小时", "天"}:
        return "duration"
    return "numeric"
