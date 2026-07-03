import os

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src.db.base import Base

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def ensure_test_database() -> None:
    test_url = make_url(TEST_DATABASE_URL)
    if not test_url.database:
        raise ValueError("TEST_DATABASE_URL must include a database name")

    admin_url = test_url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            [test_url.database],
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_url.database)))


def make_test_engine():
    ensure_test_database()
    return create_engine(TEST_DATABASE_URL)


def reset_database(engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
