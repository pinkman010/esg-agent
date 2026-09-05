from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

import pdfplumber
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE = PROJECT_ROOT / "delivery/demo/demo-report-source.json"
MODULE_NAME = "src.tools.generate_demo_report"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_demo_report_generator_module_exists():
    assert importlib.util.find_spec(MODULE_NAME) is not None


def test_demo_report_is_deterministic_extractable_and_portable(tmp_path):
    from src.tools.generate_demo_report import generate_demo_report

    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"

    generate_demo_report(SOURCE, first)
    generate_demo_report(SOURCE, second)

    assert _sha256(first) == _sha256(second)
    assert len(PdfReader(first).pages) == 8
    with pdfplumber.open(first) as pdf:
        extracted = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "ESG-Agent Demo Manufacturing Co., Ltd." in extracted
    assert "This is a fictional report generated solely" in extracted
    assert "not an assurance statement" in extracted
    forbidden = {
        os.environ.get("USERNAME", "").casefold(),
        str(PROJECT_ROOT).casefold(),
        str(tmp_path).casefold(),
    }
    combined = extracted.casefold() + first.read_bytes().decode("latin-1").casefold()
    assert all(value not in combined for value in forbidden if value)


def test_demo_report_rejects_invalid_source(tmp_path):
    from src.tools.generate_demo_report import DemoReportSourceError, generate_demo_report

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version": 1, "pages": []}', encoding="utf-8")

    try:
        generate_demo_report(invalid, tmp_path / "invalid.pdf")
    except DemoReportSourceError as exc:
        assert str(exc).startswith("DEMO_REPORT_SOURCE_INVALID:")
    else:
        raise AssertionError("invalid source was accepted")
