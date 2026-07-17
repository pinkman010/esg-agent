from pathlib import Path
from types import SimpleNamespace

import pytest

from src.services import demo_environment


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_ROOT = PROJECT_ROOT / "backend/data/runtime/demo"


def demo_settings(**overrides):
    values = {
        "app_env": "demo",
        "database_url": "postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo",
        "upload_dir": DEMO_ROOT / "uploads",
        "derived_dir": DEMO_ROOT / "derived",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeRepository:
    def __init__(self, *, actual_database="esg_agent_demo", active_runs=None, report_count=3):
        self.actual_database = actual_database
        self.active_runs = active_runs or []
        self.report_count = report_count
        self.operations = []
        self.database_cleared = False

    def get_current_database(self):
        self.operations.append("actual_database")
        return self.actual_database

    def list_active_runs(self):
        self.operations.append("active_runs")
        return self.active_runs

    def clear_demo_business_data(self):
        self.operations.append("clear_database")
        self.database_cleared = True
        return self.report_count

    def rollback(self):
        self.operations.append("rollback")


@pytest.mark.parametrize(
    ("settings_overrides", "actual_database", "confirmation", "active_runs"),
    [
        ({"app_env": "main"}, "esg_agent_demo", "RESET_DEMO", []),
        (
            {"database_url": "postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent"},
            "esg_agent_demo",
            "RESET_DEMO",
            [],
        ),
        (
            {"upload_dir": PROJECT_ROOT / "backend/data/runtime/uploads"},
            "esg_agent_demo",
            "RESET_DEMO",
            [],
        ),
        ({}, "esg_agent", "RESET_DEMO", []),
        ({}, "esg_agent_demo", "WRONG", []),
        ({}, "esg_agent_demo", "RESET_DEMO", [SimpleNamespace(run_id="run-active")]),
    ],
)
def test_reset_rejects_unsafe_conditions_before_any_write(
    settings_overrides,
    actual_database,
    confirmation,
    active_runs,
):
    repository = FakeRepository(
        actual_database=actual_database,
        active_runs=active_runs,
    )
    runtime_calls = []

    with pytest.raises(demo_environment.DemoResetError):
        demo_environment.reset_demo_environment_data(
            repository,
            demo_settings(**settings_overrides),
            confirmation=confirmation,
            runtime_cleaner=lambda *_: runtime_calls.append("clear_runtime"),
        )

    assert repository.database_cleared is False
    assert runtime_calls == []


def test_reset_validates_then_clears_database_then_runtime(monkeypatch):
    repository = FakeRepository(report_count=4)
    operations = []

    def validate(**kwargs):
        operations.append("validate")

    def get_current_database():
        operations.append("actual_database")
        return "esg_agent_demo"

    def list_active_runs():
        operations.append("active_runs")
        return []

    def clear_database():
        operations.append("clear_database")
        repository.database_cleared = True
        return 4

    repository.get_current_database = get_current_database
    repository.list_active_runs = list_active_runs
    repository.clear_demo_business_data = clear_database
    monkeypatch.setattr(demo_environment, "validate_demo_environment", validate)

    result = demo_environment.reset_demo_environment_data(
        repository,
        demo_settings(),
        confirmation="RESET_DEMO",
        runtime_cleaner=lambda *_: operations.append("clear_runtime"),
    )

    assert operations == [
        "validate",
        "actual_database",
        "active_runs",
        "clear_database",
        "validate",
        "clear_runtime",
    ]
    assert result.cleared_report_count == 4
    assert result.cleared_runtime_directories == ("uploads", "derived")


def test_runtime_failure_reports_database_was_already_cleared(monkeypatch):
    repository = FakeRepository(report_count=2)
    monkeypatch.setattr(demo_environment, "validate_demo_environment", lambda **kwargs: None)

    def fail_runtime(*args):
        raise OSError("runtime locked")

    with pytest.raises(demo_environment.DemoRuntimeCleanupError) as error:
        demo_environment.reset_demo_environment_data(
            repository,
            demo_settings(),
            confirmation="RESET_DEMO",
            runtime_cleaner=fail_runtime,
        )

    assert repository.database_cleared is True
    assert error.value.cleared_report_count == 2


def test_clear_runtime_removes_children_and_preserves_roots(tmp_path):
    uploads = tmp_path / "uploads"
    derived = tmp_path / "derived"
    uploads.mkdir()
    derived.mkdir()
    (uploads / "report.pdf").write_bytes(b"pdf")
    nested = derived / "exports/report-1"
    nested.mkdir(parents=True)
    (nested / "draft.txt").write_text("draft", encoding="utf-8")

    demo_environment.clear_runtime_directories(uploads, derived)

    assert uploads.is_dir() and not list(uploads.iterdir())
    assert derived.is_dir() and not list(derived.iterdir())


def test_clear_runtime_rejects_reparse_points_before_deleting_anything(tmp_path):
    uploads = tmp_path / "uploads"
    derived = tmp_path / "derived"
    uploads.mkdir()
    derived.mkdir()
    upload_file = uploads / "report.pdf"
    marker = derived / "linked"
    upload_file.write_bytes(b"pdf")
    marker.write_text("marker", encoding="utf-8")

    with pytest.raises(ValueError, match="reparse point"):
        demo_environment.clear_runtime_directories(
            uploads,
            derived,
            reparse_detector=lambda path: path == marker,
        )

    assert upload_file.exists()
    assert marker.exists()
