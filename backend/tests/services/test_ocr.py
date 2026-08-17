import subprocess

import pytest

import src.services.ocr as ocr


def test_run_ocr_for_pages_invokes_ocrmypdf_for_selected_pages(monkeypatch, tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    calls = []

    def fake_run(command, capture_output, text, check, env, timeout):
        calls.append((command, capture_output, text, check, env, timeout))
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
        ghostscript_cmd="C:/Program Files/gs/bin/gswin64c.exe",
        ocr_lang="chi_sim+eng",
        timeout_seconds=300,
    )

    command, capture_output, text, check, env, timeout = calls[0]
    assert command[:6] == ["ocrmypdf", "--force-ocr", "-l", "chi_sim+eng", "--pages", "2,4"]
    assert command[-2:] == [str(pdf_path), str(tmp_path / "derived" / "ocr" / "report-1" / "report-pages-2-4-ocr.pdf")]
    assert capture_output is True
    assert text is True
    assert check is False
    assert "C:/Program Files/Tesseract-OCR" in env["PATH"].replace("\\", "/")
    assert "C:/Program Files/gs/bin" in env["PATH"].replace("\\", "/")
    assert timeout == 300
    assert [result.page_number for result in results] == [2, 4]
    assert [result.text for result in results] == ["OCR energy disclosure text", "OCR energy disclosure text"]
    assert all(len(result.derived_file_sha256) == 64 for result in results)


def test_run_ocr_for_pages_raises_readable_error_when_ocrmypdf_fails(monkeypatch, tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    def fake_run(command, capture_output, text, check, env, timeout):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="[private-path] token=abc",
        )

    monkeypatch.setattr("src.services.ocr.subprocess.run", fake_run)

    assert hasattr(ocr, "OcrExecutionError")

    with pytest.raises(ocr.OcrExecutionError) as exc_info:
        ocr.run_ocr_for_pages(
            pdf_path,
            [1],
            report_id="report-1",
            derived_dir=tmp_path / "derived",
            ocrmypdf_cmd="ocrmypdf",
            ocr_lang="chi_sim+eng",
            timeout_seconds=300,
        )

    assert exc_info.value.code == "ocr_execution_failed"
    assert str(exc_info.value) == "OCR 执行失败。"
    assert "private-path" not in str(exc_info.value)
    assert "token" not in str(exc_info.value)
    assert not (tmp_path / "derived" / "ocr" / "report-1" / "report-pages-1-ocr.pdf").exists()


def test_run_ocr_for_pages_timeout_removes_partial_output(monkeypatch, tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    output_path = tmp_path / "derived" / "ocr" / "report-1" / "report-pages-77-ocr.pdf"

    def fake_run(command, capture_output, text, check, env, timeout):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"partial")
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr("src.services.ocr.subprocess.run", fake_run)

    with pytest.raises(ocr.OcrExecutionError) as exc_info:
        ocr.run_ocr_for_pages(
            pdf_path,
            [77],
            report_id="report-1",
            derived_dir=tmp_path / "derived",
            ocrmypdf_cmd="ocrmypdf",
            ghostscript_cmd="gswin64c",
            tesseract_cmd="tesseract",
            ocr_lang="chi_sim+eng",
            timeout_seconds=300,
        )

    assert exc_info.value.code == "ocr_execution_timeout"
    assert not output_path.exists()
