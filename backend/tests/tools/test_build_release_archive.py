from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_NAME = "src.tools.build_release_archive"
FIXED_GIT_DATE = "2026-01-02T03:04:04Z"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _git(repo: Path, *arguments: str, environment: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _copy(repo: Path, relative_path: str) -> None:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROJECT_ROOT / relative_path, target)


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_DATE": FIXED_GIT_DATE,
            "GIT_COMMITTER_DATE": FIXED_GIT_DATE,
        }
    )
    _git(repo, "commit", "-m", message, environment=environment)
    return _git(repo, "rev-parse", "HEAD")


def _minimal_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Delivery Test")
    _git(repo, "config", "user.email", "delivery@example.invalid")
    for relative_path in (
        ".env.example",
        "ESG-Agent.exe",
        "backend/src/tools/generate_demo_report.py",
        "backend/uv.lock",
        "delivery/demo/demo-report-source.json",
        "delivery/launcher/EsgAgentLauncher.cs",
        "delivery/launcher/EsgAgentLauncher.exe.manifest",
        "delivery/launcher/launcher-manifest.json",
        "delivery/release-policy.json",
        "delivery/toolchain-lock.json",
        "frontend/pnpm-lock.yaml",
        "scripts/delivery/Test-Preflight.ps1",
    ):
        _copy(repo, relative_path)
    (repo / ".gitignore").write_text("tmp/\n*.zip\n", encoding="utf-8")
    return repo, _commit(repo, "fixture")


def test_release_archive_builder_module_exists():
    assert importlib.util.find_spec(MODULE_NAME) is not None


def test_archive_is_commit_only_complete_and_deterministic(tmp_path):
    from src.tools.build_release_archive import build_release_archive

    repo, commit = _minimal_repo(tmp_path)
    (repo / "首页.png").write_bytes(b"untracked-user-file")
    first = build_release_archive(
        repo_root=repo,
        commit=commit,
        output_dir=repo / "tmp/first",
    )
    second = build_release_archive(
        repo_root=repo,
        commit=commit,
        output_dir=repo / "tmp/second",
    )

    assert _sha256(first.archive_path) == _sha256(second.archive_path)
    assert first.archive_sha256 == _sha256(first.archive_path)
    assert first.checksum_path.read_text(encoding="utf-8") == (
        f"{first.archive_sha256}  {first.archive_path.name}\n"
    )
    with zipfile.ZipFile(first.archive_path) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert "首页.png" not in names
        assert ".git/" not in names
        assert ".env" not in names
        assert "demo/esg-agent-synthetic-report-2025.pdf" in names
        assert names.count("demo/esg-agent-synthetic-report-2025.pdf") == 1
        assert "ESG-Agent.exe" in names
        assert all(item.date_time == (2026, 1, 2, 3, 4, 4) for item in archive.infolist())
        manifest = json.loads(archive.read("release-manifest.json"))
        payload_names = [item["path"] for item in manifest["files"]]
        assert payload_names == sorted(payload_names)
        assert payload_names == [name for name in names if name != "release-manifest.json"]
        for item in manifest["files"]:
            content = archive.read(item["path"])
            assert item["size_bytes"] == len(content)
            assert item["sha256"] == hashlib.sha256(content).hexdigest().upper()
            assert item["role"]
        assert manifest["git_commit"] == commit
        assert manifest["public_version"] == "1.5"


@pytest.mark.parametrize(
    ("unsafe_path", "content", "expected_code"),
    [
        (".env", b"DATABASE_URL=postgresql://user:password@localhost/db", "ARCHIVE_PATH_DENIED"),
        ("private.pem", b"-----BEGIN PRIVATE KEY-----\nsecret", "ARCHIVE_PATH_DENIED"),
        ("database.dump", b"database", "ARCHIVE_PATH_DENIED"),
        ("backend/data/runtime/private.txt", b"runtime", "ARCHIVE_PATH_DENIED"),
        ("unapproved.pdf", b"%PDF-1.4", "ARCHIVE_PDF_DENIED"),
        ("tools/helper.exe", b"MZother", "ARCHIVE_EXECUTABLE_DENIED"),
        ("installer.msi", b"installer", "ARCHIVE_INSTALLER_DENIED"),
        ("setup.exe", b"MZsetup", "ARCHIVE_INSTALLER_DENIED"),
    ],
)
def test_committed_unsafe_payload_is_rejected(tmp_path, unsafe_path, content, expected_code):
    from src.tools.build_release_archive import ReleaseArchiveError, build_release_archive

    repo, _ = _minimal_repo(tmp_path)
    target = repo / unsafe_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    commit = _commit(repo, f"add unsafe {unsafe_path}")

    with pytest.raises(ReleaseArchiveError) as raised:
        build_release_archive(
            repo_root=repo,
            commit=commit,
            output_dir=repo / "tmp/release",
        )
    assert raised.value.code == expected_code
    assert (repo / "tmp/release/release-build-error.txt").read_text(encoding="utf-8") == (
        f"{expected_code}\n"
    )


def test_launcher_hash_mismatch_is_rejected(tmp_path):
    from src.tools.build_release_archive import ReleaseArchiveError, build_release_archive

    repo, _ = _minimal_repo(tmp_path)
    (repo / "ESG-Agent.exe").write_bytes(b"MZtampered")
    commit = _commit(repo, "tamper launcher")

    with pytest.raises(ReleaseArchiveError) as raised:
        build_release_archive(
            repo_root=repo,
            commit=commit,
            output_dir=repo / "tmp/release",
        )
    assert raised.value.code == "LAUNCHER_HASH_MISMATCH"


def test_tracked_worktree_changes_are_rejected(tmp_path):
    from src.tools.build_release_archive import ReleaseArchiveError, build_release_archive

    repo, commit = _minimal_repo(tmp_path)
    (repo / ".env.example").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ReleaseArchiveError) as raised:
        build_release_archive(
            repo_root=repo,
            commit=commit,
            output_dir=repo / "tmp/release",
        )
    assert raised.value.code == "TRACKED_WORKTREE_DIRTY"
