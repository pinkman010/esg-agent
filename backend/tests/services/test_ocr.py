import subprocess

import pytest

import src.services.ocr as ocr


def test_run_ocr_for_pages_invokes_ocrmypdf_for_selected_pages(monkeypatch, tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    calls = []

    def fake_run(command, capture_output, text, check, env):
        calls.append((command, capture_output, text, check, env))
        output_path = tmp_path / "derived" / "ocr" / "report-1" / "report-pages-2-4-ocr.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-1.4\nocr\n")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    class FakePage:
        def extract_text(self):
            return "OCR energy disclosure text"

    class FakePdf:
        pages = [FakePage(), FakePage(), FakePage(), FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.services.ocr.subprocess.run", fake_run)
    monkeypatch.setattr("src.services.ocr.pdfplumber.open", lambda path: FakePdf())

    assert hasattr(ocr, "OcrExecutionError")

    results = ocr.run_ocr_for_pages(
        pdf_path,
        [4, 2],
        report_id="report-1",
        derived_dir=tmp_path / "derived",
        ocrmypdf_cmd="ocrmypdf",
        tesseract_cmd="C:/Program Files/Tesseract-OCR/tesseract.exe",
        ocr_lang="chi_sim+eng",
    )

    command, capture_output, text, check, env = calls[0]
    assert command[:6] == ["ocrmypdf", "--force-ocr", "-l", "chi_sim+eng", "--pages", "2,4"]
    assert command[-2:] == [str(pdf_path), str(tmp_path / "derived" / "ocr" / "report-1" / "report-pages-2-4-ocr.pdf")]
    assert capture_output is True
    assert text is True
    assert check is False
    assert "C:/Program Files/Tesseract-OCR" in env["PATH"].replace("\\", "/")
    assert [result.page_number for result in results] == [2, 4]
    assert [result.text for result in results] == ["OCR energy disclosure text", "OCR energy disclosure text"]


def test_run_ocr_for_pages_raises_readable_error_when_ocrmypdf_fails(monkeypatch, tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    def fake_run(command, capture_output, text, check, env):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="ghostscript missing")

    monkeypatch.setattr("src.services.ocr.subprocess.run", fake_run)

    assert hasattr(ocr, "OcrExecutionError")

    with pytest.raises(ocr.OcrExecutionError, match="ghostscript missing"):
        ocr.run_ocr_for_pages(
            pdf_path,
            [1],
            report_id="report-1",
            derived_dir=tmp_path / "derived",
            ocrmypdf_cmd="ocrmypdf",
            ocr_lang="chi_sim+eng",
        )

    assert not (tmp_path / "derived" / "ocr" / "report-1" / "report-pages-1-ocr.pdf").exists()
