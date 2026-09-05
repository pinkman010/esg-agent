from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _json(path: str) -> dict:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def test_toolchain_lock_matches_supported_delivery_baseline():
    toolchain = _json("delivery/toolchain-lock.json")

    assert toolchain["python"] == "3.11.14"
    assert toolchain["uv"] == "0.9.28"
    assert toolchain["node"] == "24.15.0"
    assert toolchain["pnpm"] == "11.19.0"
    assert toolchain["windows_powershell"] == {
        "recovery_source": "5.1.26100.9168",
        "recipient_minimum": "5.1",
    }
    assert toolchain["powershell_7"]["version"] == "7.6.4"
    assert toolchain["powershell_7"]["recipient_required"] is False
    assert toolchain["dotnet_framework"] == {
        "recovery_release": 533509,
        "recipient_minimum_release": 533320,
    }
    assert toolchain["launcher_compiler"] == {
        "file_version": "4.8.9221.0",
        "sha256": "46809206887326D2D24DB1EFF1F3064DE972C3451ABE766B49111450A5E08E00",
        "deterministic": False,
        "maintainer_only": True,
    }
    assert toolchain["postgresql"] == "16.14"
    assert toolchain["pgvector"] == "0.8.4"
    assert toolchain["docker"]["recovery_source"] == {
        "desktop": "4.80.0",
        "engine": "29.6.1",
        "compose": "5.1.4",
    }
    assert toolchain["docker"]["delivery_target"] == {
        "desktop_minimum": "4.89.0",
        "compose_bundled": "5.5.0",
    }


def test_release_policy_uses_public_version_1_5():
    policy = _json("delivery/release-policy.json")

    assert policy["public_version"] == "1.5"
    assert policy["package_version"] == "1.5.0"
    assert policy["archive_name"] == "esg-agent-1.5-windows-x64.zip"
    assert policy["git_tag"] == "v1.5"
    assert policy["source_mode"] == "git_archive"
    assert policy["launcher_artifact"] == "ESG-Agent.exe"
    assert policy["launcher_manifest"] == "delivery/launcher/launcher-manifest.json"
    assert policy["generated_demo_pdf"] == "demo/esg-agent-synthetic-report-2025.pdf"
    assert policy["checksum_algorithm"] == "SHA256"


def test_language_and_package_manager_versions_match_toolchain_lock():
    toolchain = _json("delivery/toolchain-lock.json")
    package = _json("frontend/package.json")

    assert (PROJECT_ROOT / ".python-version").read_text(encoding="utf-8").strip() == toolchain["python"]
    assert (PROJECT_ROOT / ".node-version").read_text(encoding="utf-8").strip() == toolchain["node"]
    assert package["packageManager"] == f"pnpm@{toolchain['pnpm']}"
    assert package["engines"]["node"] == toolchain["node"]


def test_release_policy_denies_secrets_runtime_data_and_unapproved_binaries():
    policy = _json("delivery/release-policy.json")
    denied = set(policy["deny_patterns"])

    assert {
        ".env",
        ".git/**",
        "**/node_modules/**",
        "**/.venv/**",
        "frontend/.next/**",
        "tmp/**",
        "backend/data/runtime/**",
        "**/*.dump",
        "**/*.log",
        "**/*model-response*",
        "首页.png",
        "**/*.msi",
        "**/setup.exe",
    }.issubset(denied)
    assert policy["allowed_root_executables"] == ["ESG-Agent.exe"]
    assert policy["pdf_policy"] == "deny_unless_explicitly_allowed"
