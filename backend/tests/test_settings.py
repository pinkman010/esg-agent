from pathlib import Path

from src.config.settings import Settings


def test_default_runtime_paths_resolve_from_project_root(monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    project_root = backend_dir.parent
    monkeypatch.chdir(backend_dir)

    settings = Settings()

    assert settings.upload_dir == project_root / "backend" / "data" / "runtime" / "uploads"
    assert settings.derived_dir == project_root / "backend" / "data" / "runtime" / "derived"
