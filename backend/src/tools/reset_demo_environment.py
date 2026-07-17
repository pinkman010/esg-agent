from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url

from src.config.environment_safety import validate_demo_environment
from src.services.demo_environment import clear_runtime_directories, is_reparse_point
from src.config.settings import PROJECT_ROOT, Settings


@dataclass(frozen=True)
class ResetResult:
    database_name: str
    upload_dir: Path
    derived_dir: Path
    dry_run: bool
    actions: tuple[str, ...] = ("drop/create database", "alembic upgrade head", "clear demo runtime")


@dataclass(frozen=True)
class ResetDependencies:
    count_active_connections: Callable[[str], int]
    recreate_database: Callable[[str], None]
    upgrade_database: Callable[[], None]
    clear_runtime_directories: Callable[[Path, Path], None]


def _admin_connection_url(database_url: str) -> str:
    url = make_url(database_url).set(drivername="postgresql", database="postgres")
    return url.render_as_string(hide_password=False)


def _count_active_connections(database_url: str) -> int:
    database_name = make_url(database_url).database
    with psycopg.connect(_admin_connection_url(database_url)) as connection:
        row = connection.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            [database_name],
        ).fetchone()
    return int(row[0]) if row else 0


def _recreate_database(database_url: str) -> None:
    database_name = make_url(database_url).database
    if database_name != "esg_agent_demo":
        raise ValueError("refusing to recreate a database other than esg_agent_demo")
    with psycopg.connect(_admin_connection_url(database_url), autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))


def _upgrade_database() -> None:
    config = Config(str(PROJECT_ROOT / "backend/alembic.ini"))
    command.upgrade(config, "head")


_is_reparse_point = is_reparse_point


def _clear_runtime_directories(upload_dir: Path, derived_dir: Path) -> None:
    clear_runtime_directories(upload_dir, derived_dir, reparse_detector=_is_reparse_point)


def default_dependencies() -> ResetDependencies:
    return ResetDependencies(
        count_active_connections=_count_active_connections,
        recreate_database=_recreate_database,
        upgrade_database=_upgrade_database,
        clear_runtime_directories=_clear_runtime_directories,
    )


def reset_demo_environment(
    settings: Settings,
    *,
    dry_run: bool,
    confirmation: str | None,
    dependencies: ResetDependencies | None = None,
) -> ResetResult:
    validate_demo_environment(
        app_env=settings.app_env,
        database_url=settings.database_url,
        upload_dir=settings.upload_dir,
        derived_dir=settings.derived_dir,
    )
    database_name = make_url(settings.database_url).database
    result = ResetResult(
        database_name=database_name or "",
        upload_dir=settings.upload_dir,
        derived_dir=settings.derived_dir,
        dry_run=dry_run,
    )
    if dry_run:
        return result
    if confirmation != "esg_agent_demo":
        raise ValueError("reset requires --confirm-database esg_agent_demo")

    deps = dependencies or default_dependencies()
    active_connections = deps.count_active_connections(settings.database_url)
    if active_connections:
        raise RuntimeError(
            f"found {active_connections} active connection(s) to esg_agent_demo; stop demo services first"
        )

    deps.recreate_database(settings.database_url)
    deps.upgrade_database()
    validate_demo_environment(
        app_env=settings.app_env,
        database_url=settings.database_url,
        upload_dir=settings.upload_dir,
        derived_dir=settings.derived_dir,
    )
    deps.clear_runtime_directories(settings.upload_dir, settings.derived_dir)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safely recreate the local ESG-Agent demo environment.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm-database")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = reset_demo_environment(
        Settings(),
        dry_run=args.dry_run,
        confirmation=args.confirm_database,
    )
    action = "DRY RUN" if result.dry_run else "RESET COMPLETE"
    print(f"{action}: database={result.database_name}")
    print(f"upload_dir={result.upload_dir}")
    print(f"derived_dir={result.derived_dir}")
    if result.dry_run:
        for planned_action in result.actions:
            print(f"would: {planned_action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
