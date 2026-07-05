from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from src.domain.enums import EvidenceSourceMethod, PageQualityFlag
from src.domain.models import DocumentChunk, PageExtraction
from src.services.ocr import OcrResult


@dataclass(frozen=True)
class PageQuality:
    flags: list[PageQualityFlag]
    text_length: int
    image_count: int
    table_count: int


@dataclass(frozen=True)
class ParsedDocument:
    report_id: str
    page_count: int
    pages: list[PageExtraction]
    chunks: list[DocumentChunk]
    metadata: dict
    outline: list[str]


OcrRunner = Callable[[Path, list[int]], list[OcrResult]]


def classify_page_quality(page_text: str | None, image_count: int, table_count: int) -> PageQuality:
    text = page_text or ""
    flags: list[PageQualityFlag] = []
    text_length = len(text.strip())

    if text_length >= 40:
        flags.append(PageQualityFlag.DIGITAL_TEXT)
    else:
        flags.append(PageQualityFlag.LOW_TEXT_DENSITY)

    if image_count > 0 and text_length < 40:
        flags.append(PageQualityFlag.SCANNED)

    if table_count >= 3:
        flags.append(PageQualityFlag.COMPLEX_TABLE)

    return PageQuality(flags=flags, text_length=text_length, image_count=image_count, table_count=table_count)


class DocumentParser:
    def __init__(self, ocr_runner: OcrRunner | None = None):
        self.ocr_runner = ocr_runner

    def parse_pdf(
        self,
        pdf_path: str | Path,
        report_id: str,
        source_file_hash: str,
        ocr_pages: list[int] | None = None,
    ) -> ParsedDocument:
        path = Path(pdf_path)
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        metadata = {key: str(value) for key, value in (reader.metadata or {}).items()}
        outline = self._extract_outline(reader)

        pages: list[PageExtraction] = []
        chunks: list[DocumentChunk] = []

        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                image_count = len(page.images or [])
                tables = page.extract_tables() or []
                table_count = len(tables)
                quality = classify_page_quality(text, image_count=image_count, table_count=table_count)
                pages.append(
                    PageExtraction(
                        report_id=report_id,
                        page_number=index,
                        text=text,
                        image_count=image_count,
                        table_count=table_count,
                        quality_flags=quality.flags,
                        source_method=EvidenceSourceMethod.PDFPLUMBER,
                    )
                )
                if text.strip():
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{report_id}-p{index}-pdfplumber",
                            report_id=report_id,
                            text=text,
                            source_page=index,
                            source_method=EvidenceSourceMethod.PDFPLUMBER,
                            source_file_hash=source_file_hash,
                            quality_flags=quality.flags,
                            embedding_status="not_started",
                        )
                    )

        if ocr_pages and self.ocr_runner is not None:
            for result in self.ocr_runner(path, ocr_pages):
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{report_id}-p{result.page_number}-ocr",
                        report_id=report_id,
                        text=result.text,
                        source_page=result.page_number,
                            source_method=EvidenceSourceMethod.OCR,
                            source_file_hash=source_file_hash,
                            quality_flags=[PageQualityFlag.NEEDS_MANUAL_REVIEW],
                            embedding_status="not_started",
                            metadata={"ocr_page": result.page_number},
                        )
                    )

        return ParsedDocument(
            report_id=report_id,
            page_count=page_count,
            pages=pages,
            chunks=chunks,
            metadata=metadata,
            outline=outline,
        )

    def _extract_outline(self, reader: PdfReader) -> list[str]:
        try:
            outline = reader.outline
        except Exception:
            return []
        return [str(item) for item in outline]
