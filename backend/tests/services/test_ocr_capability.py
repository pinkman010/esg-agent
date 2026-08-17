from pathlib import Path
from subprocess import CompletedProcess

import pytest

from src.config.settings import Settings
from src.services.ocr_capability import inspect_ocr_capability, require_ocr_capability
from src.services.ocr_errors import OcrPreflightError


def make_settings(**overrides) -> Settings:
    values = {
        "ocr_enabled": True,
        "ocrmypdf_cmd": "ocrmypdf",
        "ghostscript_cmd": "gswin64c",
        "tesseract_cmd": "tesseract",
        "ocr_lang": "chi_sim+eng",
        "ocr_max_pages": 5,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def install_fake_commands(
    monkeypatch,
    *,
    missing: str | None = None,
    languages: str = "chi_sim\neng\nosd\n",
    diagnostic: str = "",
) -> None:
    command_names = {
        "ocrmypdf": "ocrmypdf",
        "ghostscript": "gswin64c",
        "tesseract": "tesseract",
    }
    missing_name = command_names.get(missing or "")

    def fake_which(command: str) -> str | None:
        if command == missing_name:
            return None
        return str(Path("commands") / command)

    def fake_run(command, **kwargs):
        assert kwargs == {
            "capture_output": True,
            "text": True,
            "check": False,
            "timeout": 10,
        }
        stdout = languages if command[-1] == "--list-langs" else "1.0\n"
        return CompletedProcess(command, 0, stdout=stdout, stderr=diagnostic)

    monkeypatch.setattr("src.services.ocr_capability.shutil.which", fake_which)
    monkeypatch.setattr("src.services.ocr_capability.subprocess.run", fake_run)


@pytest.mark.parametrize(
    ("missing_command", "expected_code"),
    [
        ("ocrmypdf", "ocrmypdf_missing"),
        ("ghostscript", "ghostscript_missing"),
        ("tesseract", "tesseract_missing"),
    ],
)
def test_inspect_ocr_capability_reports_each_missing_dependency(
    monkeypatch, missing_command, expected_code
):
    install_fake_commands(monkeypatch, missing=missing_command)

    result = inspect_ocr_capability(make_settings(ocr_enabled=True))

    assert result.enabled is True
    assert result.available is False
    assert expected_code in result.dependency_codes


def test_inspect_ocr_capability_reports_missing_requested_language(monkeypatch):
    install_fake_commands(monkeypatch, languages="eng\nosd\n")

    result = inspect_ocr_capability(make_settings(ocr_enabled=True))

    assert result.available is False
    assert result.dependency_codes == ("tesseract_language_missing",)


def test_inspect_ocr_capability_reports_all_dependencies_available(monkeypatch):
    install_fake_commands(monkeypatch)

    result = inspect_ocr_capability(make_settings())

    assert result.enabled is True
    assert result.available is True
    assert result.dependency_codes == ()
    assert result.language == "chi_sim+eng"
    assert result.max_pages == 5


def test_require_ocr_capability_rejects_disabled_feature(monkeypatch):
    install_fake_commands(monkeypatch)

    with pytest.raises(OcrPreflightError) as exc_info:
        require_ocr_capability(make_settings(ocr_enabled=False))

    assert exc_info.value.code == "ocr_feature_disabled"
    assert str(exc_info.value) == "OCR 功能当前未启用。"


def test_require_ocr_capability_raises_only_safe_message(monkeypatch):
    install_fake_commands(
        monkeypatch,
        missing="ghostscript",
        diagnostic="[private-path] secret-token",
    )

    with pytest.raises(OcrPreflightError) as exc_info:
        require_ocr_capability(make_settings(ocr_enabled=True))

    assert exc_info.value.code == "ghostscript_missing"
    assert "Ghostscript" in str(exc_info.value)
    assert "private-path" not in str(exc_info.value)
    assert "secret-token" not in str(exc_info.value)
