from hashlib import sha256

import pytest

from src.tools.normalize_runtime_paths import (
    ReportPathRecord,
    assert_database_confirmation,
    build_normalization_plan,
    summarize_plan,
)


def _write(path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_dry_run_finds_one_hash_matching_candidate_without_writing(tmp_path):
    project_root = tmp_path / "project"
    upload_dir = project_root / "backend/data/runtime/demo/uploads"
    content = b"%PDF-1.4\nsynthetic\n"
    candidate = _write(upload_dir / "report.pdf", content)
    record = ReportPathRecord(
        report_id="report-1",
        stored_path=str(tmp_path / "old-checkout/backend/data/runtime/demo/uploads/report.pdf"),
        file_hash=sha256(content).hexdigest(),
    )

    decisions = build_normalization_plan(
        [record],
        project_root=project_root,
        allowed_runtime_dirs=[upload_dir],
    )

    assert decisions[0].status == "ready"
    assert decisions[0].normalized_path == "backend/data/runtime/demo/uploads/report.pdf"
    assert decisions[0].candidate_path == candidate.resolve()
    assert summarize_plan(decisions) == {"ready": 1}


def test_normalization_rejects_hash_mismatch_and_ambiguous_candidates(tmp_path):
    project_root = tmp_path / "project"
    upload_dir = project_root / "backend/data/runtime/demo/uploads"
    _write(upload_dir / "first/report.pdf", b"same")
    _write(upload_dir / "second/report.pdf", b"same")
    record = ReportPathRecord(
        report_id="report-1",
        stored_path=str(tmp_path / "old/report.pdf"),
        file_hash=sha256(b"same").hexdigest(),
    )

    decisions = build_normalization_plan(
        [record], project_root=project_root, allowed_runtime_dirs=[upload_dir]
    )
    assert decisions[0].status == "ambiguous"
    assert decisions[0].normalized_path is None

    mismatch = ReportPathRecord(
        report_id="report-2",
        stored_path=str(tmp_path / "old/other.pdf"),
        file_hash=sha256(b"missing").hexdigest(),
    )
    decisions = build_normalization_plan(
        [mismatch], project_root=project_root, allowed_runtime_dirs=[upload_dir]
    )
    assert decisions[0].status == "no_hash_match"


def test_external_absolute_upload_root_is_reported_without_conversion(tmp_path):
    project_root = tmp_path / "project"
    external_dir = tmp_path / "external"
    content = b"external"
    report_path = _write(external_dir / "report.pdf", content).resolve()
    record = ReportPathRecord(
        report_id="report-1",
        stored_path=str(report_path),
        file_hash=sha256(content).hexdigest(),
    )

    decisions = build_normalization_plan(
        [record], project_root=project_root, allowed_runtime_dirs=[external_dir]
    )

    assert decisions[0].status == "external_absolute"
    assert decisions[0].normalized_path is None


def test_apply_requires_exact_database_confirmation():
    assert_database_confirmation(actual_database="esg_agent_demo", confirmed_database="esg_agent_demo")

    with pytest.raises(ValueError, match="database confirmation mismatch"):
        assert_database_confirmation(actual_database="esg_agent_demo", confirmed_database="esg_agent")
