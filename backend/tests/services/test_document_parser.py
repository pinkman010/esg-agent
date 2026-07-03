from pypdf import PdfWriter

from src.domain.enums import EvidenceSourceMethod, PageQualityFlag
from src.services.document_parser import DocumentParser, classify_page_quality
from src.services.ocr import OcrResult


def test_classify_page_quality_marks_digital_text():
    quality = classify_page_quality("This page contains meaningful ESG disclosure text." * 3, image_count=0, table_count=0)

    assert PageQualityFlag.DIGITAL_TEXT in quality.flags
    assert PageQualityFlag.LOW_TEXT_DENSITY not in quality.flags


def test_classify_page_quality_marks_scanned_or_low_density_page():
    quality = classify_page_quality("", image_count=1, table_count=0)

    assert PageQualityFlag.SCANNED in quality.flags
    assert PageQualityFlag.LOW_TEXT_DENSITY in quality.flags


def test_document_parser_parses_blank_pdf_without_modifying_original(tmp_path):
    pdf_path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as file:
        writer.write(file)
    original_bytes = pdf_path.read_bytes()

    parsed = DocumentParser().parse_pdf(pdf_path, report_id="report-1", source_file_hash="hash-1")

    assert parsed.report_id == "report-1"
    assert parsed.page_count == 1
    assert parsed.pages[0].page_number == 1
    assert PageQualityFlag.LOW_TEXT_DENSITY in parsed.pages[0].quality_flags
    assert pdf_path.read_bytes() == original_bytes


def test_document_parser_uses_mocked_ocr_hook_for_selected_pages(tmp_path):
    pdf_path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as file:
        writer.write(file)

    def fake_ocr(path, pages):
        assert path == pdf_path
        assert pages == [1]
        return [OcrResult(page_number=1, text="OCR energy disclosure text")]

    parsed = DocumentParser(ocr_runner=fake_ocr).parse_pdf(
        pdf_path,
        report_id="report-1",
        source_file_hash="hash-1",
        ocr_pages=[1],
    )

    assert parsed.chunks[0].source_method is EvidenceSourceMethod.OCR
    assert parsed.chunks[0].text == "OCR energy disclosure text"