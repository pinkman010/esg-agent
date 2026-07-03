from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OcrResult:
    page_number: int
    text: str


class OcrNotConfiguredError(RuntimeError):
    pass


def run_ocr_for_pages(_pdf_path: Path, _pages: list[int]) -> list[OcrResult]:
    raise OcrNotConfiguredError("OCRmyPDF/Tesseract runner is not configured")