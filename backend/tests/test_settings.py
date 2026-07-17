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
