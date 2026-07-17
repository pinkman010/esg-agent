from dataclasses import dataclass
from io import BytesIO
import re

from pypdf import PdfReader


YEAR_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")
COMPANY_SUFFIX_PATTERN = re.compile(r"(?:有限责任公司|股份有限公司|有限公司|集团有限公司|集团|公司)$")


@dataclass(frozen=True)
class DetectedReportMetadata:
    page_count: int | None
    metadata: dict[str, object]


def _filename_language(filename: str) -> str | None:
    lowered = filename.lower()
    if re.search(r"(?:^|[-_.\s])zh(?:[-_.\s]|$)", lowered) or "中文" in filename:
        return "zh-CN"
    if re.search(r"(?:^|[-_.\s])en(?:[-_.\s]|$)", lowered):
        return "en"
    return None


def _company_name(text: str) -> str | None:
    candidates: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", "", raw_line).strip("：:·•-")
        if not 4 <= len(line) <= 40 or not COMPANY_SUFFIX_PATTERN.search(line):
            continue
        if re.search(r"[，。；！？,;!?]", line) or any(term in line for term in ("版权所有", "解释权", "本报告由")):
            continue
        candidates.append(line)
    unique_candidates = list(dict.fromkeys(candidates))
    return unique_candidates[0] if len(unique_candidates) == 1 else None


def detect_report_metadata(filename: str, content: bytes) -> DetectedReportMetadata:
    metadata: dict[str, object] = {"original_filename": filename}
    filename_year = YEAR_PATTERN.search(filename)
    if filename_year:
        metadata["report_year"] = int(filename_year.group(1))
    filename_language = _filename_language(filename)
    if filename_language:
        metadata["language"] = filename_language

    try:
        reader = PdfReader(BytesIO(content))
        page_count = len(reader.pages)
        cover_text = "\n".join((reader.pages[index].extract_text() or "") for index in range(min(2, page_count)))
    except Exception:
        return DetectedReportMetadata(page_count=None, metadata=metadata)

    company_name = _company_name(cover_text)
    if company_name:
        metadata["company_name"] = company_name
    cover_year = YEAR_PATTERN.search(cover_text)
    if cover_year and "report_year" not in metadata:
        metadata["report_year"] = int(cover_year.group(1))
    if CHINESE_PATTERN.search(cover_text):
        metadata["language"] = "zh-CN"

    return DetectedReportMetadata(page_count=page_count, metadata=metadata)
