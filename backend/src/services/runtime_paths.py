from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class RuntimePathError(ValueError):
    """Raised when a stored relative path escapes the project boundary."""


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def is_path_within(path: Path, root: Path) -> bool:
    candidate = _resolved(path)
    boundary = _resolved(root)
    try:
        candidate.relative_to(boundary)
    except ValueError:
        return False
    return True


def serialize_runtime_path(path: Path, *, project_root: Path) -> str:
    root = _resolved(project_root)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = _resolved(candidate)
    if is_path_within(candidate, root):
        return candidate.relative_to(root).as_posix()
    return str(candidate)


def resolve_stored_path(stored_path: str, *, project_root: Path) -> Path:
    if not stored_path.strip():
        raise RuntimePathError("stored path is empty")
    path = Path(stored_path)
    if path.is_absolute():
        return _resolved(path)

    root = _resolved(project_root)
    candidate = _resolved(root / path)
    if not is_path_within(candidate, root):
        raise RuntimePathError("stored path resolves outside project root")
    return candidate
