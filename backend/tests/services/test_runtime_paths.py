from pathlib import Path

import pytest

from src.services.runtime_paths import RuntimePathError, resolve_stored_path, serialize_runtime_path


def test_project_runtime_path_is_serialized_relative_and_resolved(tmp_path):
    project_root = tmp_path / "project"
    report_path = project_root / "backend" / "data" / "runtime" / "demo" / "uploads" / "report.pdf"

    stored = serialize_runtime_path(report_path, project_root=project_root)

    assert stored == "backend/data/runtime/demo/uploads/report.pdf"
    assert resolve_stored_path(stored, project_root=project_root) == report_path.resolve()


def test_relative_stored_path_cannot_escape_project_root(tmp_path):
    project_root = tmp_path / "project"

    with pytest.raises(RuntimePathError, match="outside project root"):
        resolve_stored_path("../private/report.pdf", project_root=project_root)


def test_legacy_absolute_stored_path_remains_readable(tmp_path):
    project_root = tmp_path / "project"
    legacy_path = (tmp_path / "legacy" / "report.pdf").resolve()

    assert resolve_stored_path(str(legacy_path), project_root=project_root) == legacy_path


def test_explicit_external_upload_path_remains_absolute(tmp_path):
    project_root = tmp_path / "project"
    external_path = (tmp_path / "external-uploads" / "report.pdf").resolve()

    stored = serialize_runtime_path(external_path, project_root=project_root)

    assert Path(stored).is_absolute()
    assert Path(stored) == external_path
