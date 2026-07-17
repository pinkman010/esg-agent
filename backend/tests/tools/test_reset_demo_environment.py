from pathlib import Path
from unittest.mock import Mock

import pytest

from src.config.settings import Settings
import src.tools.reset_demo_environment as reset_module
from src.tools.reset_demo_environment import ResetDependencies, reset_demo_environment


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def demo_settings(**overrides):
    values = {
        "app_env": "demo",
        "database_url": "postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo",
        "upload_dir": PROJECT_ROOT / "backend/data/runtime/demo/uploads",
        "derived_dir": PROJECT_ROOT / "backend/data/runtime/demo/derived",
    }
    values.update(overrides)
    return Settings(**values)


def dependencies(active_connections=0):
    return ResetDependencies(
        count_active_connections=Mock(return_value=active_connections),
        recreate_database=Mock(),
        upgrade_database=Mock(),
        clear_runtime_directories=Mock(),
    )


def test_dry_run_only_reports_targets():
    deps = dependencies()

    result = reset_demo_environment(demo_settings(), dry_run=True, confirmation=None, dependencies=deps)

    assert result.database_name == "esg_agent_demo"
    assert result.dry_run is True
    assert result.actions == ("drop/create database", "alembic upgrade head", "clear demo runtime")
    deps.count_active_connections.assert_not_called()
    deps.recreate_database.assert_not_called()
    deps.upgrade_database.assert_not_called()
    deps.clear_runtime_directories.assert_not_called()


def test_reset_requires_exact_database_confirmation():
    deps = dependencies()

    with pytest.raises(ValueError, match="--confirm-database esg_agent_demo"):
        reset_demo_environment(demo_settings(), dry_run=False, confirmation="esg_agent", dependencies=deps)

    deps.recreate_database.assert_not_called()


def test_reset_rejects_active_demo_connections():
    deps = dependencies(active_connections=2)

    with pytest.raises(RuntimeError, match="2 active connection"):
        reset_demo_environment(demo_settings(), dry_run=False, confirmation="esg_agent_demo", dependencies=deps)

    deps.recreate_database.assert_not_called()


def test_reset_recreates_migrates_then_clears_runtime():
    calls = []
    deps = ResetDependencies(
        count_active_connections=lambda _: 0,
        recreate_database=lambda _: calls.append("recreate"),
        upgrade_database=lambda: calls.append("upgrade"),
        clear_runtime_directories=lambda *_: calls.append("clear"),
    )

    result = reset_demo_environment(
        demo_settings(),
        dry_run=False,
        confirmation="esg_agent_demo",
        dependencies=deps,
    )

    assert result.dry_run is False
    assert calls == ["recreate", "upgrade", "clear"]


def test_migration_failure_does_not_clear_runtime():
    deps = dependencies()
    deps.upgrade_database.side_effect = RuntimeError("migration failed")

    with pytest.raises(RuntimeError, match="migration failed"):
        reset_demo_environment(
            demo_settings(),
            dry_run=False,
            confirmation="esg_agent_demo",
            dependencies=deps,
        )

    deps.clear_runtime_directories.assert_not_called()


def test_reset_validates_again_before_clearing_runtime(monkeypatch):
    deps = dependencies()
    validate = Mock()
    monkeypatch.setattr(reset_module, "validate_demo_environment", validate)

    reset_demo_environment(
        demo_settings(),
        dry_run=False,
        confirmation="esg_agent_demo",
        dependencies=deps,
    )

    assert validate.call_count == 2
    assert validate.call_args_list[0] == validate.call_args_list[1]


def test_clear_runtime_removes_children_and_preserves_roots(tmp_path):
    uploads = tmp_path / "demo/uploads"
    derived = tmp_path / "demo/derived"
    uploads.mkdir(parents=True)
    derived.mkdir(parents=True)
    (uploads / "report.pdf").write_bytes(b"pdf")
    nested = derived / "exports/report-1"
    nested.mkdir(parents=True)
    (nested / "draft.txt").write_text("draft", encoding="utf-8")

    reset_module._clear_runtime_directories(uploads, derived)

    assert uploads.is_dir() and not list(uploads.iterdir())
    assert derived.is_dir() and not list(derived.iterdir())


def test_clear_runtime_rejects_reparse_points_before_deleting_anything(monkeypatch, tmp_path):
    uploads = tmp_path / "demo/uploads"
    derived = tmp_path / "demo/derived"
    uploads.mkdir(parents=True)
    derived.mkdir(parents=True)
    upload_file = uploads / "report.pdf"
    marker = derived / "linked"
    upload_file.write_bytes(b"pdf")
    marker.write_text("marker", encoding="utf-8")
    monkeypatch.setattr(reset_module, "_is_reparse_point", lambda path: path == marker)

    with pytest.raises(ValueError, match="reparse point"):
        reset_module._clear_runtime_directories(uploads, derived)

    assert upload_file.exists()
    assert marker.exists()
