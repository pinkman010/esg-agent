from pathlib import Path

import pytest

from src.config.environment_safety import validate_demo_environment


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_UPLOADS = PROJECT_ROOT / "backend/data/runtime/demo/uploads"
DEMO_DERIVED = PROJECT_ROOT / "backend/data/runtime/demo/derived"


def validate(**overrides):
    values = {
        "app_env": "demo",
        "database_url": "postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo",
        "upload_dir": DEMO_UPLOADS,
        "derived_dir": DEMO_DERIVED,
    }
    values.update(overrides)
    validate_demo_environment(**values)


def test_demo_environment_accepts_expected_database_and_paths():
    validate()


@pytest.mark.parametrize("app_env", ["main", "test"])
def test_demo_environment_rejects_non_demo_app_env(app_env):
    with pytest.raises(ValueError, match="APP_ENV=demo"):
        validate(app_env=app_env)


@pytest.mark.parametrize("database_name", ["esg_agent", "esg_agent_test", "postgres"])
def test_demo_environment_rejects_non_demo_database(database_name):
    with pytest.raises(ValueError, match="esg_agent_demo"):
        validate(database_url=f"postgresql+psycopg://esg_agent:esg_agent@localhost:5432/{database_name}")


@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("upload_dir", PROJECT_ROOT / "backend/data/runtime/uploads"),
        ("derived_dir", PROJECT_ROOT / "backend/data/runtime/derived"),
        ("upload_dir", PROJECT_ROOT / "backend/data/runtime"),
        ("derived_dir", PROJECT_ROOT),
        ("upload_dir", PROJECT_ROOT.parent / "outside/uploads"),
    ],
)
def test_demo_environment_rejects_paths_outside_demo_runtime(field, path):
    with pytest.raises(ValueError, match="runtime/demo"):
        validate(**{field: path})
