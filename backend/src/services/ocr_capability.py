from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from src.config.settings import Settings
from src.services.ocr_errors import OcrPreflightError


@dataclass(frozen=True)
class OcrCapability:
    enabled: bool
    available: bool
    dependency_codes: tuple[str, ...]
    language: str
    max_pages: int


def inspect_ocr_capability(settings: Settings) -> OcrCapability:
    dependency_codes: list[str] = []

    ocrmypdf_command = _resolve_command(settings.ocrmypdf_cmd)
    if not _command_succeeds(ocrmypdf_command, "--version"):
        dependency_codes.append("ocrmypdf_missing")

    ghostscript_command = _resolve_command(
        settings.ghostscript_cmd,
        fallbacks=("gswin64c", "gswin32c", "gs"),
    )
    if not _command_succeeds(ghostscript_command, "--version"):
        dependency_codes.append("ghostscript_missing")

    tesseract_command = _resolve_command(settings.tesseract_cmd, fallbacks=("tesseract",))
    language_output = _command_output(tesseract_command, "--list-langs")
    if language_output is None:
        dependency_codes.append("tesseract_missing")
    elif not _requested_languages(settings.ocr_lang).issubset(_available_languages(language_output)):
        dependency_codes.append("tesseract_language_missing")

    codes = tuple(dependency_codes)
    return OcrCapability(
        enabled=settings.ocr_enabled,
        available=settings.ocr_enabled and not codes,
        dependency_codes=codes,
        language=settings.ocr_lang,
        max_pages=settings.ocr_max_pages,
    )


def require_ocr_capability(settings: Settings) -> OcrCapability:
    capability = inspect_ocr_capability(settings)
    if not capability.enabled:
        raise OcrPreflightError("ocr_feature_disabled")
    if capability.dependency_codes:
        raise OcrPreflightError(capability.dependency_codes[0])
    return capability


def _resolve_command(configured: str, *, fallbacks: tuple[str, ...] = ()) -> str | None:
    candidates = (configured,) if configured.strip() else fallbacks
    for candidate in candidates:
        path = Path(candidate)
        if path.is_absolute():
            if path.is_file():
                return str(path)
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _command_succeeds(command: str | None, argument: str) -> bool:
    return _command_output(command, argument) is not None


def _command_output(command: str | None, argument: str) -> str | None:
    if command is None:
        return None
    try:
        completed = subprocess.run(
            [command, argument],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _requested_languages(language: str) -> set[str]:
    return {item.strip() for item in language.split("+") if item.strip()}


def _available_languages(output: str) -> set[str]:
    return {line.strip() for line in output.splitlines() if line.strip()}
