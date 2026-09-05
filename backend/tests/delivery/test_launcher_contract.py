from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = PROJECT_ROOT / "ESG-Agent.exe"
SOURCE = PROJECT_ROOT / "delivery/launcher/EsgAgentLauncher.cs"
APP_MANIFEST = PROJECT_ROOT / "delivery/launcher/EsgAgentLauncher.exe.manifest"
LAUNCHER_MANIFEST = PROJECT_ROOT / "delivery/launcher/launcher-manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict:
    return json.loads(LAUNCHER_MANIFEST.read_text(encoding="utf-8"))


def _fake_layout(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "delivery"
    scripts = root / "scripts/delivery"
    scripts.mkdir(parents=True)
    executable = shutil.copy2(LAUNCHER, root / LAUNCHER.name)
    script = r"""[CmdletBinding()]
param([switch]$OpenBrowser)
$record = [ordered]@{
  script = $MyInvocation.MyCommand.Name
  open_browser = [bool]$OpenBrowser
}
Add-Content -LiteralPath $env:ESG_AGENT_LAUNCHER_TEST_LOG -Value ($record | ConvertTo-Json -Compress)
Write-Output $env:ESG_AGENT_LAUNCHER_TEST_SECRET
if ($env:ESG_AGENT_LAUNCHER_TEST_HOLD_PIPE -eq "1") {
  & $env:ComSpec /d /s /c `
    'start "" /b powershell.exe -NoProfile -Command "Start-Sleep -Seconds 4"'
}
exit [int]$env:ESG_AGENT_LAUNCHER_TEST_EXIT
"""
    for name in ("Start-EsgAgent.ps1", "Test-EsgAgent.ps1", "Stop-EsgAgent.ps1"):
        (scripts / name).write_text(script, encoding="utf-8")
    return Path(executable), root


def _run_launcher(
    executable: Path,
    root: Path,
    args: tuple[str, ...],
    *,
    exit_code: int = 0,
):
    log_path = root / "launcher-test.log"
    if log_path.exists():
        log_path.unlink()
    environment = os.environ.copy()
    environment.update(
        {
            "ESG_AGENT_LAUNCHER_NONINTERACTIVE": "1",
            "ESG_AGENT_LAUNCHER_TEST_LOG": str(log_path),
            "ESG_AGENT_LAUNCHER_TEST_EXIT": str(exit_code),
            "ESG_AGENT_LAUNCHER_TEST_SECRET": "launcher-secret-must-not-leak",
            "ESG_AGENT_LAUNCHER_TEST_HOLD_PIPE": "0",
        }
    )
    completed = subprocess.run(
        [str(executable), *args],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    records = []
    if log_path.exists():
        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    return completed, records


def test_launcher_allows_only_fixed_actions():
    assert _manifest()["actions"] == {
        "double_click": {"script": "Start-EsgAgent.ps1", "argument": "-OpenBrowser"},
        "--no-browser": {"script": "Start-EsgAgent.ps1", "argument": None},
        "--status": {"script": "Test-EsgAgent.ps1", "argument": None},
        "--stop": {"script": "Stop-EsgAgent.ps1", "argument": None},
    }


def test_launcher_manifest_matches_tracked_inputs_and_binary():
    manifest = _manifest()

    assert _sha256(SOURCE) == manifest["source_sha256"].casefold()
    assert _sha256(APP_MANIFEST) == manifest["app_manifest_sha256"].casefold()
    assert _sha256(LAUNCHER) == manifest["artifact"]["sha256"].casefold()
    assert LAUNCHER.stat().st_size == manifest["artifact"]["size_bytes"]
    assert manifest["public_version"] == "1.5"
    assert manifest["package_version"] == "1.5.0"
    assert manifest["assembly_version"] == "1.5.0.0"
    assert manifest["file_version"] == "1.5.0.0"
    assert manifest["product_version"] == "1.5"
    assert manifest["compiler"]["file_version"] == "4.8.9221.0"
    assert manifest["compiler"]["sha256"].casefold() == (
        "46809206887326D2D24DB1EFF1F3064DE972C3451ABE766B49111450A5E08E00".casefold()
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher contract")
def test_launcher_fixture_maps_actions_and_redacts_secret(tmp_path):
    executable, root = _fake_layout(tmp_path)
    expected = {
        (): ("Start-EsgAgent.ps1", True),
        ("--no-browser",): ("Start-EsgAgent.ps1", False),
        ("--status",): ("Test-EsgAgent.ps1", False),
        ("--stop",): ("Stop-EsgAgent.ps1", False),
    }

    for arguments, (script, open_browser) in expected.items():
        completed, records = _run_launcher(executable, root, arguments)
        assert completed.returncode == 0
        assert records == [{"script": script, "open_browser": open_browser}]
        assert "launcher-secret-must-not-leak" not in completed.stdout
        assert "launcher-secret-must-not-leak" not in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher contract")
def test_launcher_preserves_script_exit_code_and_rejects_invalid_arguments(tmp_path):
    executable, root = _fake_layout(tmp_path)

    completed, records = _run_launcher(executable, root, ("--status",), exit_code=23)
    assert completed.returncode == 23
    assert len(records) == 1

    for arguments in (("--unknown",), ("--status", "--stop"), ("--status", "--status")):
        completed, records = _run_launcher(executable, root, arguments)
        assert completed.returncode == 64
        assert records == []
        assert "INVALID_ARGUMENTS" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher contract")
def test_launcher_rejects_layout_without_fixed_script(tmp_path):
    executable, root = _fake_layout(tmp_path)
    (root / "scripts/delivery/Test-EsgAgent.ps1").unlink()

    completed, records = _run_launcher(executable, root, ("--status",))

    assert completed.returncode == 10
    assert records == []
    assert "LAUNCHER_LAYOUT_INVALID" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows launcher contract")
def test_launcher_does_not_wait_for_inherited_output_pipe(tmp_path):
    executable, root = _fake_layout(tmp_path)
    log_path = root / "launcher-test.log"
    environment = os.environ.copy()
    environment.update(
        {
            "ESG_AGENT_LAUNCHER_NONINTERACTIVE": "1",
            "ESG_AGENT_LAUNCHER_TEST_LOG": str(log_path),
            "ESG_AGENT_LAUNCHER_TEST_EXIT": "0",
            "ESG_AGENT_LAUNCHER_TEST_SECRET": "launcher-secret-must-not-leak",
            "ESG_AGENT_LAUNCHER_TEST_HOLD_PIPE": "1",
        }
    )

    started = time.monotonic()
    process = subprocess.Popen(
        [str(executable), "--status"],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return_code = process.wait(timeout=2.5)
    elapsed = time.monotonic() - started
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert return_code == 0
    assert len(records) == 1
    assert elapsed < 2.5
