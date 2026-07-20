from pathlib import Path

import pytest

from src.config.settings import Settings


def test_default_runtime_paths_resolve_from_project_root(monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    project_root = backend_dir.parent
    monkeypatch.chdir(backend_dir)

    settings = Settings()

    assert settings.upload_dir == project_root / "backend" / "data" / "runtime" / "uploads"
    assert settings.derived_dir == project_root / "backend" / "data" / "runtime" / "derived"


def test_default_environment_is_main():
    assert Settings().app_env == "main"


def test_llm_defaults_match_deepseek_json_configuration():
    settings = Settings()

    assert settings.openai_compatible_api_base == "https://api.deepseek.com"
    assert settings.llm_model == "deepseek-v4-flash"
    assert settings.llm_thinking_type == "enabled"
    assert settings.llm_reasoning_effort == "high"
    assert settings.llm_response_format == "json_object"
    assert settings.llm_max_tokens == 4096
    assert settings.llm_timeout_seconds == 120
    assert settings.llm_max_retries == 2
    assert settings.llm_retry_delay_seconds == 2
    assert settings.llm_max_concurrency == 8
    assert settings.llm_max_calls_per_run == 200
    assert settings.llm_prompt_version == "deepseek-gri-assist-v1"


def test_llm_settings_reject_unsafe_or_out_of_range_values():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(openai_compatible_api_base="http://api.deepseek.com")
    with pytest.raises(ValueError):
        Settings(llm_max_concurrency=17)
    with pytest.raises(ValueError):
        Settings(llm_max_retries=4)
    with pytest.raises(ValueError):
        Settings(llm_max_tokens=511)
    with pytest.raises(ValueError):
        Settings(llm_max_tokens=8193)


def test_llm_configuration_summary_never_exposes_api_key():
    secret = "sk-do-not-return-this-value"
    summary = Settings(openai_compatible_api_key=secret).llm_configuration_summary()

    assert summary["api_key_present"] is True
    assert secret not in str(summary)
    assert "api_key" not in summary


def test_demo_runtime_paths_resolve_from_project_root(monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    project_root = backend_dir.parent
    monkeypatch.chdir(backend_dir)

    settings = Settings(
        app_env="demo",
        database_url="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo",
        upload_dir=Path("backend/data/runtime/demo/uploads"),
        derived_dir=Path("backend/data/runtime/demo/derived"),
    )

    assert settings.upload_dir == project_root / "backend/data/runtime/demo/uploads"
    assert settings.derived_dir == project_root / "backend/data/runtime/demo/derived"


def test_demo_example_env_file_is_parseable(monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    env_file = backend_dir / ".env.demo.example"
    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("BACKEND_CORS_ORIGINS", raising=False)

    settings = Settings(_env_file=env_file)

    assert settings.app_env == "demo"
    assert settings.backend_cors_origins == ["http://localhost:3000"]
    assert settings.database_url.endswith("/esg_agent_demo")
    assert 'BACKEND_CORS_ORIGINS=\'["http://localhost:3000"]\'' in env_file.read_text(
        encoding="utf-8"
    )


def test_demo_settings_reject_main_database():
    with pytest.raises(ValueError, match="esg_agent_demo"):
        Settings(
            app_env="demo",
            database_url="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent",
            upload_dir=Path("backend/data/runtime/demo/uploads"),
            derived_dir=Path("backend/data/runtime/demo/derived"),
        )


def test_demo_settings_reject_main_runtime_paths():
    with pytest.raises(ValueError, match="runtime/demo"):
        Settings(
            app_env="demo",
            database_url="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo",
            upload_dir=Path("backend/data/runtime/uploads"),
            derived_dir=Path("backend/data/runtime/derived"),
        )
