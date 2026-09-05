from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


BACKEND_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HEAD = "0012_chunk_embeddings"
DOWNGRADE_REVISION = "0011_ai_suggestions"
DATABASE_PREFIX = "esg_agent_migration_test_"
FORBIDDEN_DATABASES = {"esg_agent", "esg_agent_demo", "postgres", "template0", "template1"}


def _run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
    )


def test_empty_database_upgrade_downgrade_upgrade_roundtrip():
    database_url = os.environ.get("MIGRATION_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("MIGRATION_TEST_DATABASE_URL is required for migration round-trip")

    url = make_url(database_url)
    database_name = url.database or ""
    assert database_name.startswith(DATABASE_PREFIX)
    assert database_name not in FORBIDDEN_DATABASES

    admin_url = url.set(drivername="postgresql", database="postgres")
    admin_connection_url = admin_url.render_as_string(hide_password=False)
    with psycopg.connect(admin_connection_url, autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", [database_name]
        ).fetchone()
        assert exists is None, "migration test database must be unique and empty"
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    engine = create_engine(database_url)
    try:
        _run_alembic(database_url, "upgrade", "head")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == EXPECTED_HEAD
            assert connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )

        _run_alembic(database_url, "downgrade", DOWNGRADE_REVISION)
        assert "document_chunk_embeddings" not in inspect(engine).get_table_names()

        _run_alembic(database_url, "upgrade", "head")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == EXPECTED_HEAD
    finally:
        engine.dispose()
        with psycopg.connect(admin_connection_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                [database_name],
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
