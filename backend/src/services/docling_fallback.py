from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DoclingFallbackResult:
    status: str
    message: str = ""


def run_docling_fallback(_pdf_path: Path, _pages: list[int]) -> DoclingFallbackResult:
    return DoclingFallbackResult(status="not_configured", message="Docling fallback is not configured")