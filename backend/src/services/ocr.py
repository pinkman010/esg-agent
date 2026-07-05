from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

import pdfplumber


@dataclass(frozen=True)
class OcrResult:
    page_number: int
    text: str


class OcrExecutionError(RuntimeError):
    pass


class OcrNotConfiguredError(OcrExecutionError):
    pass


def run_ocr_for_pages(
    pdf_path: Path,
    pages: list[int],
    *,
    report_id: str,
    derived_dir: Path,
    ocrmypdf_cmd: str = "ocrmypdf",
    tesseract_cmd: str = "",
    ocr_lang: str = "chi_sim+eng",
) -> list[OcrResult]:
    selected_pages = sorted({page for page in pages if page > 0})
    if not selected_pages:
        return []
    if not ocrmypdf_cmd:
        raise OcrNotConfiguredError("OCRmyPDF command is not configured")

    path = Path(pdf_path)
    output_path = _ocr_output_path(path, selected_pages, report_id=report_id, derived_dir=Path(derived_dir))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ocrmypdf_cmd,
        "--force-ocr",
        "-l",
        ocr_lang,
        "--pages",
        _format_pages(selected_pages),
        str(path),
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=_subprocess_env(tesseract_cmd),
    )
    if completed.returncode != 0:
        if output_path.exists():
            output_path.unlink()
        detail = completed.stderr.strip() or completed.stdout.strip() or f"OCRmyPDF exited with code {completed.returncode}"
        raise OcrExecutionError(detail)

    results: list[OcrResult] = []
    with pdfplumber.open(output_path) as pdf:
        for page_number in selected_pages:
            if page_number > len(pdf.pages):
                continue
            text = pdf.pages[page_number - 1].extract_text() or ""
            results.append(OcrResult(page_number=page_number, text=text))
    return results


def _ocr_output_path(pdf_path: Path, pages: list[int], *, report_id: str, derived_dir: Path) -> Path:
    page_key = "-".join(str(page) for page in pages)
    return derived_dir / "ocr" / report_id / f"{pdf_path.stem}-pages-{page_key}-ocr.pdf"


def _format_pages(pages: list[int]) -> str:
    return ",".join(str(page) for page in pages)


def _subprocess_env(tesseract_cmd: str) -> dict[str, str]:
    env = os.environ.copy()
    if not tesseract_cmd:
        return env
    tesseract_path = Path(tesseract_cmd)
    tesseract_dir = str(tesseract_path if tesseract_path.is_dir() else tesseract_path.parent)
    env["PATH"] = f"{tesseract_dir}{os.pathsep}{env.get('PATH', '')}"
    env["TESSERACT_CMD"] = tesseract_cmd
    return env
