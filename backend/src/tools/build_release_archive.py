from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


RUNTIME_PLACEHOLDERS = {
    "backend/data/runtime/.gitkeep",
    "backend/data/runtime/uploads/.gitkeep",
    "backend/data/runtime/derived/.gitkeep",
    "backend/data/runtime/exports/.gitkeep",
}
CONFIG_TEMPLATE_SUFFIXES = (".env.example", ".env.demo.example")
SENSITIVE_NAME_SUFFIXES = ("PASSWORD", "SECRET", "TOKEN", "API_KEY")
SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".crt", ".cer"}
INSTALLER_EXTENSIONS = {".msi", ".msix", ".appx"}


class ReleaseArchiveError(RuntimeError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class ReleaseArchiveResult:
    archive_path: Path
    archive_sha256: str
    checksum_path: Path
    git_commit: str


def _run_git(repo_root: Path, *arguments: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        capture_output=True,
        text=not binary,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseArchiveError("GIT_COMMAND_FAILED", "unable to read the requested Git commit")
    return completed.stdout


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _load_json(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseArchiveError(code, f"invalid JSON metadata: {path.name}") from exc
    if not isinstance(value, dict):
        raise ReleaseArchiveError(code, f"unexpected JSON shape: {path.name}")
    return value


def _assert_tracked_worktree_clean(repo_root: Path) -> None:
    status = _run_git(repo_root, "status", "--porcelain", "--untracked-files=no")
    if str(status).strip():
        raise ReleaseArchiveError(
            "TRACKED_WORKTREE_DIRTY", "tracked files must match the selected commit"
        )


def _extract_git_archive(repo_root: Path, commit: str, build_root: Path, staging: Path) -> None:
    tar_path = build_root / "source.tar"
    _run_git(
        repo_root,
        "-c",
        "core.autocrlf=false",
        "archive",
        "--format=tar",
        f"--output={tar_path}",
        commit,
    )
    staging.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:") as archive:
        for member in archive.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ReleaseArchiveError("GIT_ARCHIVE_INVALID", "archive contains an unsafe path")
            target = staging.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ReleaseArchiveError(
                    "GIT_ARCHIVE_INVALID", "archive links and special files are not supported"
                )
            source = archive.extractfile(member)
            if source is None:
                raise ReleaseArchiveError("GIT_ARCHIVE_INVALID", "archive file could not be read")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def _load_staged_generator(staging: Path):
    generator_path = staging / "backend/src/tools/generate_demo_report.py"
    if not generator_path.is_file():
        raise ReleaseArchiveError(
            "DEMO_GENERATOR_MISSING", "the selected commit has no demo report generator"
        )
    spec = importlib.util.spec_from_file_location(
        "_esg_agent_staged_demo_generator", generator_path
    )
    if spec is None or spec.loader is None:
        raise ReleaseArchiveError(
            "DEMO_GENERATOR_INVALID", "the staged demo report generator cannot be loaded"
        )
    module = importlib.util.module_from_spec(spec)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ReleaseArchiveError(
            "DEMO_GENERATOR_INVALID", "the staged demo report generator failed to load"
        ) from exc
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


def _validate_launcher(staging: Path, policy: dict[str, Any], toolchain: dict[str, Any]) -> None:
    launcher_manifest_path = staging / "delivery/launcher/launcher-manifest.json"
    launcher_manifest = _load_json(launcher_manifest_path, code="LAUNCHER_MANIFEST_INVALID")
    expected_artifact = policy.get("launcher_artifact")
    expected_manifest = policy.get("launcher_manifest")
    if expected_artifact != "ESG-Agent.exe" or expected_manifest != (
        "delivery/launcher/launcher-manifest.json"
    ):
        raise ReleaseArchiveError(
            "RELEASE_POLICY_INVALID", "launcher paths are not the approved fixed paths"
        )
    paths = {
        "artifact": staging / expected_artifact,
        "source": staging / "delivery/launcher/EsgAgentLauncher.cs",
        "app_manifest": staging / "delivery/launcher/EsgAgentLauncher.exe.manifest",
    }
    if any(not path.is_file() for path in paths.values()):
        raise ReleaseArchiveError("LAUNCHER_ARTIFACT_MISSING", "launcher bundle is incomplete")
    expected_hashes = {
        "artifact": (launcher_manifest.get("artifact") or {}).get("sha256"),
        "source": launcher_manifest.get("source_sha256"),
        "app_manifest": launcher_manifest.get("app_manifest_sha256"),
    }
    if any(
        not isinstance(expected_hashes[name], str)
        or _sha256_file(path).casefold() != expected_hashes[name].casefold()
        for name, path in paths.items()
    ):
        raise ReleaseArchiveError(
            "LAUNCHER_HASH_MISMATCH", "launcher inputs do not match launcher-manifest.json"
        )
    if (
        launcher_manifest.get("public_version") != policy.get("public_version")
        or launcher_manifest.get("package_version") != policy.get("package_version")
    ):
        raise ReleaseArchiveError(
            "LAUNCHER_VERSION_MISMATCH", "launcher and release policy versions differ"
        )
    compiler = launcher_manifest.get("compiler") or {}
    locked_compiler = toolchain.get("launcher_compiler") or {}
    if (
        compiler.get("file_version") != locked_compiler.get("file_version")
        or str(compiler.get("sha256", "")).casefold()
        != str(locked_compiler.get("sha256", "")).casefold()
    ):
        raise ReleaseArchiveError(
            "LAUNCHER_COMPILER_MISMATCH", "launcher compiler record differs from toolchain lock"
        )


def _is_config_template(relative_path: str) -> bool:
    return relative_path == ".env.example" or relative_path.endswith(CONFIG_TEMPLATE_SUFFIXES)


def _matches_denied_pattern(relative_path: str, patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatchcase(relative_path, pattern)
        or (
            pattern.startswith("**/")
            and fnmatch.fnmatchcase(relative_path, pattern.removeprefix("**/"))
        )
        for pattern in patterns
    )


def _validate_path(relative_path: str, policy: dict[str, Any]) -> None:
    lowered = relative_path.casefold()
    suffix = PurePosixPath(relative_path).suffix.casefold()
    filename = PurePosixPath(relative_path).name.casefold()
    if "__pycache__" in PurePosixPath(relative_path).parts or suffix in {".pyc", ".pyo"}:
        raise ReleaseArchiveError(
            "ARCHIVE_GENERATED_FILE_DENIED", "generated Python bytecode is not allowed"
        )
    if relative_path in RUNTIME_PLACEHOLDERS:
        return
    if filename == "setup.exe" or suffix in INSTALLER_EXTENSIONS:
        raise ReleaseArchiveError(
            "ARCHIVE_INSTALLER_DENIED", "installer payloads are outside this delivery"
        )
    if suffix == ".exe":
        if relative_path not in set(policy.get("allowed_root_executables") or []):
            raise ReleaseArchiveError(
                "ARCHIVE_EXECUTABLE_DENIED", "only the approved root launcher is allowed"
            )
        return
    if suffix == ".pdf":
        if relative_path not in set(policy.get("allowed_pdf_paths") or []):
            raise ReleaseArchiveError(
                "ARCHIVE_PDF_DENIED", "only the generated synthetic demo PDF is allowed"
            )
        return
    if _is_config_template(relative_path):
        return
    if suffix in SENSITIVE_EXTENSIONS:
        raise ReleaseArchiveError(
            "ARCHIVE_PATH_DENIED", "credential and certificate files are not allowed"
        )
    if (
        lowered == ".env"
        or lowered.endswith("/.env")
        or lowered.startswith("backend/data/runtime/")
        or _matches_denied_pattern(relative_path, list(policy.get("deny_patterns") or []))
    ):
        raise ReleaseArchiveError(
            "ARCHIVE_PATH_DENIED", "a denied path is tracked by the selected commit"
        )


def _validate_config_template(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeError, OSError) as exc:
        raise ReleaseArchiveError(
            "CONFIG_TEMPLATE_INVALID", "configuration template is not UTF-8 text"
        ) from exc
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        normalized_name = name.strip().upper()
        normalized_value = value.strip().strip('"').strip("'")
        is_sensitive = any(
            normalized_name == suffix or normalized_name.endswith(f"_{suffix}")
            for suffix in SENSITIVE_NAME_SUFFIXES
        )
        if is_sensitive and normalized_value:
            raise ReleaseArchiveError(
                "CONFIG_TEMPLATE_SECRET_PRESENT", "a sensitive template value is not empty"
            )
        if re.search(r"postgres(?:ql)?(?:\+\w+)?://[^\s:/]+:[^@\s]+@", normalized_value):
            raise ReleaseArchiveError(
                "CONFIG_TEMPLATE_SECRET_PRESENT", "a database password is embedded in a template"
            )


def _validate_payload(staging: Path, policy: dict[str, Any]) -> list[Path]:
    files = sorted(
        (path for path in staging.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(staging).as_posix(),
    )
    for path in files:
        relative = path.relative_to(staging).as_posix()
        _validate_path(relative, policy)
        if _is_config_template(relative):
            _validate_config_template(path)
    return files


def _role_for(relative_path: str) -> str:
    if relative_path == "ESG-Agent.exe" or relative_path.startswith("delivery/launcher/"):
        return "windows_launcher"
    if relative_path == "demo/esg-agent-synthetic-report-2025.pdf":
        return "synthetic_demo_report"
    if relative_path.startswith("delivery/demo/"):
        return "synthetic_demo_source"
    if relative_path.endswith(("uv.lock", "pnpm-lock.yaml")):
        return "dependency_lock"
    if _is_config_template(relative_path):
        return "configuration_template"
    if relative_path.startswith("scripts/delivery/"):
        return "delivery_operation"
    if relative_path.startswith("docs/") or relative_path == "README.md":
        return "documentation"
    if relative_path.startswith("delivery/"):
        return "delivery_metadata"
    if relative_path.startswith("backend/data/"):
        return "product_data"
    return "source"


def _zip_timestamp(epoch_seconds: int) -> tuple[int, int, int, int, int, int]:
    value = datetime.fromtimestamp(epoch_seconds, tz=UTC)
    year = max(1980, min(2107, value.year))
    return (year, value.month, value.day, value.hour, value.minute, value.second // 2 * 2)


def _write_deterministic_zip(staging: Path, archive_path: Path, *, epoch_seconds: int) -> None:
    timestamp = _zip_timestamp(epoch_seconds)
    files = sorted(
        (path for path in staging.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(staging).as_posix(),
    )
    temporary = archive_path.with_suffix(archive_path.suffix + ".tmp")
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in files:
            relative = path.relative_to(staging).as_posix()
            info = zipfile.ZipInfo(relative, date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    os.replace(temporary, archive_path)


def _write_failure_summary(output_dir: Path, code: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "release-build-error.txt").write_text(f"{code}\n", encoding="utf-8")


def build_release_archive(
    *,
    repo_root: Path,
    commit: str,
    output_dir: Path,
) -> ReleaseArchiveResult:
    repo_root = Path(repo_root).resolve()
    output_dir = Path(output_dir).resolve()
    build_root: Path | None = None
    try:
        if not (repo_root / ".git").exists():
            raise ReleaseArchiveError("GIT_REPOSITORY_REQUIRED", "repo-root is not a Git worktree")
        _assert_tracked_worktree_clean(repo_root)
        resolved_commit = str(_run_git(repo_root, "rev-parse", "--verify", f"{commit}^{{commit}}" )).strip()
        epoch_seconds = int(str(_run_git(repo_root, "show", "-s", "--format=%ct", resolved_commit)).strip())
        tmp_root = (repo_root / "tmp").resolve()
        tmp_root.mkdir(parents=True, exist_ok=True)
        build_root = Path(tempfile.mkdtemp(prefix="release-build-", dir=tmp_root)).resolve()
        if tmp_root not in build_root.parents:
            raise ReleaseArchiveError("RELEASE_STAGING_INVALID", "staging escaped the repository tmp directory")
        staging = build_root / "staging"
        _extract_git_archive(repo_root, resolved_commit, build_root, staging)

        policy = _load_json(staging / "delivery/release-policy.json", code="RELEASE_POLICY_INVALID")
        toolchain = _load_json(staging / "delivery/toolchain-lock.json", code="TOOLCHAIN_LOCK_INVALID")
        _validate_launcher(staging, policy, toolchain)

        generated_relative = policy.get("generated_demo_pdf")
        if generated_relative != "demo/esg-agent-synthetic-report-2025.pdf":
            raise ReleaseArchiveError(
                "RELEASE_POLICY_INVALID", "generated demo PDF path is not approved"
            )
        generator = _load_staged_generator(staging)
        try:
            generator.generate_demo_report(
                staging / "delivery/demo/demo-report-source.json",
                staging / generated_relative,
            )
        except Exception as exc:
            raise ReleaseArchiveError(
                "DEMO_GENERATION_FAILED", "synthetic demo report could not be generated"
            ) from exc

        payload_files = _validate_payload(staging, policy)
        manifest_files = []
        for path in payload_files:
            relative = path.relative_to(staging).as_posix()
            manifest_files.append(
                {
                    "path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256_file(path),
                    "role": _role_for(relative),
                }
            )
        commit_time = datetime.fromtimestamp(epoch_seconds, tz=UTC).isoformat().replace("+00:00", "Z")
        release_manifest = {
            "schema_version": 1,
            "public_version": policy.get("public_version"),
            "package_version": policy.get("package_version"),
            "git_commit": resolved_commit,
            "git_commit_timestamp_utc": commit_time,
            "checksum_algorithm": "SHA256",
            "toolchain_lock_sha256": _sha256_file(staging / "delivery/toolchain-lock.json"),
            "launcher_sha256": _sha256_file(staging / "ESG-Agent.exe"),
            "files": manifest_files,
        }
        (staging / "release-manifest.json").write_text(
            json.dumps(release_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _validate_payload(staging, policy)

        output_dir.mkdir(parents=True, exist_ok=True)
        archive_name = policy.get("archive_name")
        if not isinstance(archive_name, str) or Path(archive_name).name != archive_name:
            raise ReleaseArchiveError("RELEASE_POLICY_INVALID", "archive_name must be a file name")
        archive_path = output_dir / archive_name
        _write_deterministic_zip(staging, archive_path, epoch_seconds=epoch_seconds)
        archive_hash = _sha256_file(archive_path)
        checksum_path = output_dir / "esg-agent-1.5-SHA256SUMS.txt"
        checksum_path.write_text(f"{archive_hash}  {archive_name}\n", encoding="utf-8")
        error_summary = output_dir / "release-build-error.txt"
        if error_summary.exists():
            error_summary.unlink()
        return ReleaseArchiveResult(
            archive_path=archive_path,
            archive_sha256=archive_hash,
            checksum_path=checksum_path,
            git_commit=resolved_commit,
        )
    except ReleaseArchiveError as exc:
        _write_failure_summary(output_dir, exc.code)
        raise
    finally:
        if build_root is not None and build_root.exists():
            tmp_root = (repo_root / "tmp").resolve()
            if tmp_root in build_root.resolve().parents:
                shutil.rmtree(build_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic ESG-Agent release archive")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_release_archive(
            repo_root=args.repo_root,
            commit=args.commit,
            output_dir=args.output_dir,
        )
    except ReleaseArchiveError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "RELEASE_ARCHIVE_BUILT "
        f"path={result.archive_path.name} sha256={result.archive_sha256} commit={result.git_commit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
