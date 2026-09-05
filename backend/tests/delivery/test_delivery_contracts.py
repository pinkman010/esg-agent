from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _json(path: str) -> dict:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def _env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (PROJECT_ROOT / path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator, f"invalid environment line in {path}: {raw_line}"
        values[key] = value
    return values


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
    assert toolchain["powershell_7"]["version"] == "7.6.5"
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


def test_delivery_environment_templates_are_safe_by_default():
    root_env = _env(".env.example")
    backend_env = _env("backend/.env.example")
    demo_env = _env("backend/.env.demo.example")
    frontend_env = _env("frontend/.env.example")
    all_example_text = "\n".join(
        (PROJECT_ROOT / path).read_text(encoding="utf-8")
        for path in (
            ".env.example",
            "backend/.env.example",
            "backend/.env.demo.example",
            "frontend/.env.example",
        )
    )

    assert root_env["APP_ENV"] == "demo"
    assert root_env["COMPOSE_PROJECT_NAME"] == "esg-agent"
    assert root_env["DATABASE_URL"] == ""
    assert root_env["POSTGRES_PASSWORD"] == ""
    assert root_env["OCR_ENABLED"] == "false"
    assert root_env["EMBEDDING_ENABLED"] == "false"
    assert root_env["POSTGRES_PORT"] == "5432"
    assert root_env["BACKEND_PORT"] == "8000"
    assert root_env["FRONTEND_PORT"] == "3000"
    assert root_env["STARTUP_TIMEOUT_SECONDS"] == "180"
    assert root_env["OPENAI_COMPATIBLE_API_KEY"] == ""
    assert root_env["EMBEDDING_API_KEY"] == ""
    assert backend_env["GHOSTSCRIPT_CMD"] == ""
    assert backend_env["OCR_TIMEOUT_SECONDS"] == "300"
    assert backend_env["LLM_PROMPT_VERSION"] == "deepseek-gri-assist-v1.2"
    assert demo_env["APP_ENV"] == "demo"
    assert demo_env["OCR_ENABLED"] == "false"
    assert demo_env["EMBEDDING_ENABLED"] == "false"
    assert demo_env["UPLOAD_DIR"] == "backend/data/runtime/demo/uploads"
    assert demo_env["DERIVED_DIR"] == "backend/data/runtime/demo/derived"
    assert frontend_env["NEXT_PUBLIC_API_BASE_URL"] == "http://localhost:8000"
    assert "esg_agent:esg_agent" not in all_example_text
    assert "POSTGRES_PASSWORD=esg_agent" not in all_example_text


def test_compose_uses_pinned_image_secret_input_and_healthcheck():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    toolchain = _json("delivery/toolchain-lock.json")

    assert toolchain["postgres_image"] in compose
    assert "${POSTGRES_PASSWORD:?" in compose
    assert "POSTGRES_PASSWORD: esg_agent" not in compose
    assert "${POSTGRES_PORT:-5432}:5432" in compose
    assert "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB" in compose
    assert "interval: 5s" in compose
    assert "timeout: 5s" in compose
    assert "retries: 20" in compose


def test_windows_lifecycle_scripts_follow_safety_contract():
    script_root = PROJECT_ROOT / "scripts/delivery"
    expected = {
        "Delivery.Common.ps1",
        "Test-Preflight.ps1",
        "Initialize-Environment.ps1",
        "Initialize-Database.ps1",
        "Start-EsgAgent.ps1",
        "Stop-EsgAgent.ps1",
        "Test-EsgAgent.ps1",
        "New-EsgAgentBackup.ps1",
        "Restore-EsgAgentBackup.ps1",
    }
    texts = {
        name: (script_root / name).read_text(encoding="utf-8")
        for name in expected
    }
    combined = "\n".join(texts.values()).casefold()

    assert "$psscriptroot" in combined
    assert "uv sync --frozen" in texts["Initialize-Environment.ps1"]
    assert "pnpm install --frozen-lockfile" in texts["Initialize-Environment.ps1"]
    assert "corepack" in texts["Initialize-Environment.ps1"]
    assert "['http://localhost:" not in texts["Initialize-Environment.ps1"]
    assert "uv run --frozen --no-sync uvicorn" in texts["Start-EsgAgent.ps1"]
    assert "pnpm start" in texts["Start-EsgAgent.ps1"]
    assert "--reload" not in texts["Start-EsgAgent.ps1"]
    assert "-WindowStyle Hidden" in texts["Start-EsgAgent.ps1"]
    assert "-PassThru" in texts["Start-EsgAgent.ps1"]
    assert "-RedirectStandardOutput" in texts["Start-EsgAgent.ps1"]
    assert "-RedirectStandardError" in texts["Start-EsgAgent.ps1"]
    assert "[switch]$OpenBrowser" in texts["Start-EsgAgent.ps1"]
    assert "http://localhost:" in texts["Start-EsgAgent.ps1"]
    assert "Get-EsgProcessManifestPath" in texts["Start-EsgAgent.ps1"]
    assert "Get-EsgProcessManifestPath" in texts["Stop-EsgAgent.ps1"]
    assert "processes.json" in texts["Delivery.Common.ps1"]
    assert "root_hash" in texts["Start-EsgAgent.ps1"]
    assert "root_hash" in texts["Stop-EsgAgent.ps1"]
    assert "Get-NetTCPConnection" in texts["Test-Preflight.ps1"]
    assert "excludedportrange" in texts["Test-Preflight.ps1"]
    assert "PORT_IN_USE" in texts["Test-Preflight.ps1"]
    assert "PORT_EXCLUDED" in texts["Test-Preflight.ps1"]
    assert "StrictDelivery" in texts["Test-Preflight.ps1"]
    assert "STARTUP_TIMEOUT_SECONDS" in texts["Start-EsgAgent.ps1"]
    assert "BACKEND_PORT" in texts["Start-EsgAgent.ps1"]
    assert "FRONTEND_PORT" in texts["Start-EsgAgent.ps1"]
    assert "BACKEND_PORT" in texts["Test-EsgAgent.ps1"]
    assert "FRONTEND_PORT" in texts["Test-EsgAgent.ps1"]
    assert "-IncludeDatabase" in texts["Stop-EsgAgent.ps1"]
    assert "docker compose" in texts["Stop-EsgAgent.ps1"]

    for forbidden in (
        "reset to factory defaults",
        "clean up data",
        "docker compose down -v",
        "docker_data.vhdx",
        "delete excludedportrange",
        "remove-item -recurse $home",
    ):
        assert forbidden not in combined


def test_delivery_scripts_do_not_embed_secrets_or_full_database_urls_in_results():
    script_root = PROJECT_ROOT / "scripts/delivery"
    preflight = (script_root / "Test-Preflight.ps1").read_text(encoding="utf-8")
    health = (script_root / "Test-EsgAgent.ps1").read_text(encoding="utf-8")

    assert "OPENAI_COMPATIBLE_API_KEY" in preflight
    assert "EMBEDDING_API_KEY" in preflight
    assert "api_key_present" in preflight
    assert "DATABASE_URL=" not in preflight
    assert "DATABASE_URL=" not in health
