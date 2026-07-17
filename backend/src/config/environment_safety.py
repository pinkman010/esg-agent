from pathlib import Path

from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_RUNTIME_ROOT = (PROJECT_ROOT / "backend/data/runtime/demo").resolve()


def validate_demo_environment(
    *,
    app_env: str,
    database_url: str,
    upload_dir: Path,
    derived_dir: Path,
) -> None:
    """Validate demo reset targets without changing databases or files."""
    if app_env != "demo":
        raise ValueError("demo reset requires APP_ENV=demo")

    database_name = make_url(database_url).database
    if database_name != "esg_agent_demo":
        raise ValueError("demo reset requires database esg_agent_demo")

    for name, value in (("UPLOAD_DIR", upload_dir), ("DERIVED_DIR", derived_dir)):
        resolved = Path(value).resolve()
        if resolved == DEMO_RUNTIME_ROOT or not resolved.is_relative_to(DEMO_RUNTIME_ROOT):
            raise ValueError(f"{name} must be a child of backend/data/runtime/demo")
