from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import subprocess

import pdfplumber

from src.services.ocr_errors import OcrExecutionError


@dataclass(frozen=True)
class OcrResult:
    page_number: int
    text: str
    derived_file_sha256: str


class OcrNotConfiguredError(OcrExecutionError):
    def __init__(self) -> None:
        super().__init__("ocrmypdf_missing")


def run_ocr_for_pages(
    pdf_path: Path,
    pages: list[int],
    *,
    report_id: str,
    derived_dir: Path,
    ocrmypdf_cmd: str = "ocrmypdf",
    ghostscript_cmd: str = "",
    tesseract_cmd: str = "",
    ocr_lang: str = "chi_sim+eng",
    timeout_seconds: int = 300,
) -> list[OcrResult]:
    selected_pages = sorted({page for page in pages if page > 0})
    if not selected_pages:
        return []
    if not ocrmypdf_cmd:
        raise OcrNotConfiguredError()

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
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=_subprocess_env(tesseract_cmd, ghostscript_cmd),
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output_path.unlink(missing_ok=True)
        raise OcrExecutionError("ocr_execution_timeout") from exc
    if completed.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise OcrExecutionError("ocr_execution_failed")

    derived_hash = sha256(output_path.read_bytes()).hexdigest()
    results: list[OcrResult] = []
    with pdfplumber.open(output_path) as pdf:
        for page_number in selected_pages:
            if page_number > len(pdf.pages):
                continue
            text = pdf.pages[page_number - 1].extract_text() or ""
            results.append(
                OcrResult(
                    page_number=page_number,
                    text=text,
                    derived_file_sha256=derived_hash,
                )
            )
    return results


def _ocr_output_path(pdf_path: Path, pages: list[int], *, report_id: str, derived_dir: Path) -> Path:
    page_key = "-".join(str(page) for page in pages)
    return derived_dir / "ocr" / report_id / f"{pdf_path.stem}-pages-{page_key}-ocr.pdf"


def _format_pages(pages: list[int]) -> str:
    return ",".join(str(page) for page in pages)


def _subprocess_env(tesseract_cmd: str, ghostscript_cmd: str) -> dict[str, str]:
    env = os.environ.copy()
    command_dirs = []
    for configured_command in (tesseract_cmd, ghostscript_cmd):
        if not configured_command:
            continue
        command_path = Path(configured_command)
        command_dir = command_path if command_path.is_dir() else command_path.parent
        if command_dir != Path("."):
            command_dirs.append(str(command_dir))
    if command_dirs:
        prefix = os.pathsep.join(dict.fromkeys(command_dirs))
        env["PATH"] = f"{prefix}{os.pathsep}{env.get('PATH', '')}"
    if tesseract_cmd:
        env["TESSERACT_CMD"] = tesseract_cmd
    return env
