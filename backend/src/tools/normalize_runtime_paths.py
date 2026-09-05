from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Sequence

from src.services.runtime_paths import is_path_within, resolve_stored_path, serialize_runtime_path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ReportPathRecord:
    report_id: str
    stored_path: str
    file_hash: str


@dataclass(frozen=True)
class NormalizationDecision:
    report_id: str
    status: str
    normalized_path: str | None = None
    candidate_path: Path | None = None
    expected_hash: str | None = None


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_files(roots: Sequence[Path]) -> list[Path]:
    files: dict[Path, None] = {}
    for root in roots:
        resolved_root = root.resolve(strict=False)
        if not resolved_root.exists():
            continue
        for path in resolved_root.rglob("*"):
            if path.is_file():
                files[path.resolve(strict=False)] = None
    return sorted(files, key=lambda item: item.as_posix())


def build_normalization_plan(
    records: Iterable[ReportPathRecord],
    *,
    project_root: Path,
    allowed_runtime_dirs: Sequence[Path],
) -> list[NormalizationDecision]:
    root = project_root.resolve(strict=False)
    allowed_roots = [path.resolve(strict=False) for path in allowed_runtime_dirs]
    internal_roots = [path for path in allowed_roots if is_path_within(path, root)]
    external_roots = [path for path in allowed_roots if not is_path_within(path, root)]
    candidates = _unique_files(internal_roots)
    hash_cache: dict[Path, str] = {}
    decisions: list[NormalizationDecision] = []

    for record in records:
        stored = Path(record.stored_path)
        if not stored.is_absolute():
            resolve_stored_path(record.stored_path, project_root=root)
            decisions.append(
                NormalizationDecision(report_id=record.report_id, status="already_relative")
            )
            continue

        current = stored.resolve(strict=False)
        if any(is_path_within(current, external_root) for external_root in external_roots):
            decisions.append(
                NormalizationDecision(report_id=record.report_id, status="external_absolute")
            )
            continue

        matching: list[Path] = []
        for candidate in candidates:
            if candidate not in hash_cache:
                hash_cache[candidate] = _file_sha256(candidate)
            candidate_hash = hash_cache[candidate]
            if candidate_hash.casefold() == record.file_hash.casefold():
                matching.append(candidate)

        if not matching:
            decisions.append(
                NormalizationDecision(report_id=record.report_id, status="no_hash_match")
            )
            continue
        if len(matching) > 1:
            decisions.append(
                NormalizationDecision(report_id=record.report_id, status="ambiguous")
            )
            continue

        candidate = matching[0]
        decisions.append(
            NormalizationDecision(
                report_id=record.report_id,
                status="ready",
                normalized_path=serialize_runtime_path(candidate, project_root=root),
                candidate_path=candidate,
                expected_hash=record.file_hash,
            )
        )
    return decisions


def summarize_plan(decisions: Iterable[NormalizationDecision]) -> dict[str, int]:
    return dict(sorted(Counter(decision.status for decision in decisions).items()))


def assert_database_confirmation(*, actual_database: str, confirmed_database: str) -> None:
    if not confirmed_database or confirmed_database != actual_database:
        raise ValueError("database confirmation mismatch")


def _apply_ready_updates(session, decisions: Sequence[NormalizationDecision]) -> int:
    from sqlalchemy import text

    updated = 0
    for decision in decisions:
        if decision.status != "ready":
            continue
        if decision.candidate_path is None or decision.expected_hash is None:
            raise ValueError("ready decision is incomplete")
        if _file_sha256(decision.candidate_path).casefold() != decision.expected_hash.casefold():
            raise ValueError(f"candidate hash changed for {decision.report_id}")
        result = session.execute(
            text(
                "UPDATE reports SET stored_path = :stored_path "
                "WHERE report_id = :report_id AND file_hash = :file_hash"
            ),
            {
                "stored_path": decision.normalized_path,
                "report_id": decision.report_id,
                "file_hash": decision.expected_hash,
            },
        )
        if result.rowcount != 1:
            raise ValueError(f"report changed before update: {decision.report_id}")
        updated += 1
    return updated


def _public_result(decisions: Sequence[NormalizationDecision], *, mode: str, updated: int) -> dict:
    return {
        "mode": mode,
        "counts": summarize_plan(decisions),
        "updated": updated,
        "reports": [
            {
                "report_id": decision.report_id,
                "status": decision.status,
                "normalized_path": decision.normalized_path,
            }
            for decision in decisions
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize portable report runtime paths")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", default="")
    args = parser.parse_args(argv)

    from sqlalchemy import text

    from src.config.settings import get_settings
    from src.db.session import SessionLocal

    settings = get_settings()
    with SessionLocal() as session:
        actual_database = session.scalar(text("SELECT current_database()"))
        rows = session.execute(
            text("SELECT report_id, stored_path, file_hash FROM reports ORDER BY report_id")
        ).mappings()
        records = [
            ReportPathRecord(
                report_id=row["report_id"],
                stored_path=row["stored_path"],
                file_hash=row["file_hash"],
            )
            for row in rows
        ]
        decisions = build_normalization_plan(
            records,
            project_root=PROJECT_ROOT,
            allowed_runtime_dirs=[settings.upload_dir],
        )
        updated = 0
        if args.apply:
            assert_database_confirmation(
                actual_database=actual_database,
                confirmed_database=args.confirm_database,
            )
            updated = _apply_ready_updates(session, decisions)
            session.commit()

    print(
        json.dumps(
            _public_result(decisions, mode="apply" if args.apply else "dry-run", updated=updated),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
